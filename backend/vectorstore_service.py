#!/usr/bin/env python3

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json

import chromadb
from chromadb.config import Settings
import ollama
from langchain_text_splitters import RecursiveCharacterTextSplitter
import PyPDF2
import docx

logger = logging.getLogger(__name__)

class VectorStoreService:
    """Service for managing vector embeddings of domain knowledge documents"""

    def __init__(self, persist_directory: str = "./data/vectordb"):
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )

        # Create or get collections
        self.collection_name = "domain_knowledge"
        self.collection = self.chroma_client.get_or_create_collection(name=self.collection_name)

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )

        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Document processing queue
        self.processing_queue = asyncio.Queue()

        logger.info(f"VectorStoreService initialized with ChromaDB at {persist_directory}")

    def _extract_text_from_file(self, file_path: str, file_type: str) -> str:
        """Extract text content from various file types"""
        try:
            if file_type.lower() == 'pdf':
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text() + "\n"
                    return text

            elif file_type.lower() in ['docx', 'doc']:
                doc = docx.Document(file_path)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text

            elif file_type.lower() == 'txt':
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()

            elif file_type.lower() == 'md':
                with open(file_path, 'r', encoding='utf-8') as file:
                    return file.read()

            else:
                raise ValueError(f"Unsupported file type: {file_type}")

        except Exception as e:
            logger.error(f"Failed to extract text from {file_path}: {e}")
            raise

    def _extract_text_from_content(self, file_content: bytes, file_type: str) -> str:
        """Extract text content from various file types using content bytes"""
        try:
            if file_type.lower() == 'pdf':
                from io import BytesIO
                pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text

            elif file_type.lower() in ['docx', 'doc']:
                from io import BytesIO
                doc = docx.Document(BytesIO(file_content))
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text

            elif file_type.lower() in ['txt', 'md']:
                # Try to decode as UTF-8, fallback to latin-1 if that fails
                try:
                    return file_content.decode('utf-8')
                except UnicodeDecodeError:
                    return file_content.decode('latin-1')

            else:
                logger.warning(f"Unsupported file type: {file_type}")
                return ""

        except Exception as e:
            logger.error(f"Failed to extract text from content: {e}")
            return ""

    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embeddings using Ollama nomic-embed-text"""
        try:
            response = ollama.embeddings(
                model='nomic-embed-text',
                prompt=text
            )
            return response['embedding']
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks for embedding"""
        return self.text_splitter.split_text(text)

    def _generate_chunk_id(self, doc_id: str, chunk_index: int) -> str:
        """Generate unique ID for a document chunk"""
        return f"{doc_id}_chunk_{chunk_index}"

    async def add_document_async(self, project_id: str, file_content: bytes, filename: str,
                               equipment_id: Optional[str] = None,
                               sensor_type: Optional[str] = None,
                               document_type: str = "general") -> str:
        """Add a document to the vector store asynchronously"""
        doc_id = hashlib.md5(f"{project_id}_{filename}_{equipment_id or ''}_{sensor_type or ''}".encode()).hexdigest()

        # Extract file extension
        file_type = Path(filename).suffix[1:].lower()  # Remove the dot

        # Submit to processing queue
        await self.processing_queue.put({
            'doc_id': doc_id,
            'project_id': project_id,
            'file_content': file_content,
            'filename': filename,
            'file_type': file_type,
            'equipment_id': equipment_id,
            'sensor_type': sensor_type,
            'document_type': document_type
        })

        # Start processing if not already running
        asyncio.create_task(self._process_documents())

        return doc_id

    async def _process_documents(self):
        """Process documents from the queue asynchronously"""
        while not self.processing_queue.empty():
            doc_data = await self.processing_queue.get()

            try:
                await self._process_single_document(doc_data)
            except Exception as e:
                logger.error(f"Failed to process document {doc_data['doc_id']}: {e}")
            finally:
                self.processing_queue.task_done()

    async def _process_single_document(self, doc_data: Dict[str, Any]):
        """Process a single document: extract text, chunk, embed, and store"""
        doc_id = doc_data['doc_id']
        file_content = doc_data['file_content']

        logger.info(f"Processing document {doc_id}: {doc_data['filename']}")

        # Extract text
        text = await asyncio.get_event_loop().run_in_executor(
            self.executor, self._extract_text_from_content, file_content, doc_data['file_type']
        )

        if not text.strip():
            logger.warning(f"No text extracted from {doc_data['filename']}")
            return

        # Chunk text
        chunks = await asyncio.get_event_loop().run_in_executor(
            self.executor, self._chunk_text, text
        )

        logger.info(f"Document {doc_id} split into {len(chunks)} chunks")

        # Generate embeddings and store
        documents = []
        metadatas = []
        ids = []

        for i, chunk in enumerate(chunks):
            # Generate embedding
            embedding = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._generate_embedding, chunk
            )

            chunk_id = self._generate_chunk_id(doc_id, i)

            documents.append(chunk)
            # Create metadata, filtering out None values
            metadata = {
                'doc_id': doc_id,
                'project_id': doc_data['project_id'],
                'filename': doc_data['filename'],
                'document_type': doc_data['document_type'],
                'chunk_index': i,
                'total_chunks': len(chunks)
            }

            # Only add non-None values
            if doc_data.get('equipment_id') is not None:
                metadata['equipment_id'] = doc_data['equipment_id']
            if doc_data.get('sensor_type') is not None:
                metadata['sensor_type'] = doc_data['sensor_type']

            metadatas.append(metadata)
            ids.append(chunk_id)

        # Store in ChromaDB
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Document {doc_id} processed and stored with {len(chunks)} chunks")

    async def search_similar(self, query: str, project_id: str,
                           equipment_id: Optional[str] = None,
                           sensor_type: Optional[str] = None,
                           limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents using semantic similarity"""
        try:
            # Generate embedding for query
            query_embedding = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._generate_embedding, query
            )

            # Build search filter
            where_filter = {"project_id": project_id}
            if equipment_id:
                where_filter["equipment_id"] = equipment_id
            if sensor_type:
                where_filter["sensor_type"] = sensor_type

            # Search in ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                where=where_filter,
                n_results=limit,
                include=['documents', 'metadatas', 'distances']
            )

            # Format results
            formatted_results = []
            if results['documents'] and results['metadatas']:
                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    formatted_results.append({
                        'content': doc,
                        'metadata': metadata,
                        'similarity_score': 1 - distance,  # Convert distance to similarity
                        'filename': metadata.get('filename'),
                        'equipment_id': metadata.get('equipment_id'),
                        'sensor_type': metadata.get('sensor_type'),
                        'document_type': metadata.get('document_type')
                    })

            return formatted_results

        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return []

    def delete_document(self, doc_id: str):
        """Delete all chunks of a document"""
        try:
            # Find all chunks for this document
            results = self.collection.get(
                where={"doc_id": doc_id},
                include=['metadatas']
            )

            if results['ids']:
                # Delete all chunks
                self.collection.delete(ids=results['ids'])
                logger.info(f"Deleted document {doc_id} with {len(results['ids'])} chunks")
                return True
            else:
                logger.warning(f"Document {doc_id} not found")
                return False

        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    def get_document_stats(self, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics about stored documents"""
        try:
            if project_id:
                results = self.collection.get(where={"project_id": project_id})
                total_chunks = len(results['ids'])
            else:
                total_chunks = self.collection.count()

            # Get unique documents
            if project_id:
                metadatas = results['metadatas']
            else:
                all_results = self.collection.get(include=['metadatas'])
                metadatas = all_results['metadatas']

            unique_docs = set()
            equipment_docs = set()
            file_types = {}

            for metadata in metadatas:
                if metadata:
                    doc_id = metadata.get('doc_id')
                    if doc_id:
                        unique_docs.add(doc_id)

                    equipment_id = metadata.get('equipment_id')
                    if equipment_id:
                        equipment_docs.add(f"{doc_id}_{equipment_id}")

                    filename = metadata.get('filename')
                    if filename:
                        ext = Path(filename).suffix[1:].lower()
                        file_types[ext] = file_types.get(ext, 0) + 1

            return {
                'total_chunks': total_chunks,
                'unique_documents': len(unique_docs),
                'equipment_specific_documents': len(equipment_docs),
                'file_types': file_types
            }

        except Exception as e:
            logger.error(f"Failed to get document stats: {e}")
            return {
                'total_chunks': 0,
                'unique_documents': 0,
                'equipment_specific_documents': 0,
                'file_types': {}
            }

    def clear_project_documents(self, project_id: str):
        """Delete all documents for a project"""
        try:
            results = self.collection.get(where={"project_id": project_id})
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"Cleared {len(results['ids'])} chunks for project {project_id}")
                return len(results['ids'])
            return 0
        except Exception as e:
            logger.error(f"Failed to clear project documents: {e}")
            return 0

# Global vector store instance
vector_store = VectorStoreService()
