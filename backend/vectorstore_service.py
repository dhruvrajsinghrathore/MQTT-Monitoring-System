#!/usr/bin/env python3
"""
Vector Store Service for Domain Knowledge Documents

Uses Unstructured.io for robust document parsing (text, tables, OCR),
per-project ChromaDB collections, and hierarchical affiliation-based search.
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import hashlib
import json
import tempfile

import chromadb
from chromadb.config import Settings
import ollama
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Unstructured imports for document parsing
try:
    from unstructured.partition.auto import partition
    from unstructured.partition.pdf import partition_pdf
    from unstructured.partition.docx import partition_docx
    from unstructured.partition.text import partition_text
    from unstructured.partition.md import partition_md
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    logging.warning("Unstructured library not available. Falling back to basic extraction.")

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing vector embeddings of domain knowledge documents
    
    Features:
    - Per-project ChromaDB collections for isolation
    - Unstructured.io for text, table, and OCR extraction
    - Page number tracking in metadata
    - Hierarchical affiliation search (sensor → equipment → general)
    """

    def __init__(self, persist_directory: str = "./data/vectordb"):
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )

        # Initialize text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )

        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Document processing queue
        self.processing_queue = asyncio.Queue()

        # Cache for project collections
        self._collection_cache: Dict[str, Any] = {}

        logger.info(f"VectorStoreService initialized with ChromaDB at {persist_directory}")
        logger.info(f"Unstructured.io available: {UNSTRUCTURED_AVAILABLE}")

    def _get_project_collection(self, project_id: str):
        """Get or create a ChromaDB collection for a specific project"""
        collection_name = f"domain_knowledge_{project_id}"
        
        # Check cache first
        if collection_name in self._collection_cache:
            return self._collection_cache[collection_name]
        
        # Create or get collection
        collection = self.chroma_client.get_or_create_collection(name=collection_name)
        self._collection_cache[collection_name] = collection
        
        logger.info(f"Got collection for project {project_id}: {collection_name}")
        return collection

    def delete_project_collection(self, project_id: str) -> bool:
        """Delete the entire collection for a project"""
        collection_name = f"domain_knowledge_{project_id}"
        try:
            self.chroma_client.delete_collection(name=collection_name)
            # Remove from cache
            if collection_name in self._collection_cache:
                del self._collection_cache[collection_name]
            logger.info(f"Deleted collection for project {project_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection for project {project_id}: {e}")
            return False

    def _extract_with_unstructured(self, file_content: bytes, file_type: str) -> List[Dict[str, Any]]:
        """
        Extract text and tables from document using Unstructured.io
        
        Returns list of elements with:
        - text: The extracted text content
        - page_number: Page number (if available)
        - element_type: Type of element (NarrativeText, Table, Title, etc.)
        """
        if not UNSTRUCTURED_AVAILABLE:
            # Fallback to basic extraction
            return self._extract_basic(file_content, file_type)
        
        elements_data = []
        
        try:
            # Write content to temp file (Unstructured works better with files)
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_type}") as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            try:
                # Use appropriate partition function based on file type
                if file_type.lower() == 'pdf':
                    # Use partition_pdf with OCR strategy for scanned docs
                    elements = partition_pdf(
                        filename=tmp_path,
                        strategy="hi_res",  # Uses OCR when needed
                        infer_table_structure=True,  # Extract tables
                        include_page_breaks=True
                    )
                elif file_type.lower() in ['docx', 'doc']:
                    elements = partition_docx(filename=tmp_path)
                elif file_type.lower() == 'txt':
                    elements = partition_text(filename=tmp_path)
                elif file_type.lower() == 'md':
                    elements = partition_md(filename=tmp_path)
                else:
                    # Auto-detect for other types
                    elements = partition(filename=tmp_path)
                
                # Process elements
                for element in elements:
                    element_text = str(element)
                    if not element_text.strip():
                        continue
                    
                    # Get metadata
                    metadata = element.metadata if hasattr(element, 'metadata') else None
                    page_number = None
                    if metadata and hasattr(metadata, 'page_number'):
                        page_number = metadata.page_number
                    
                    # Get element type
                    element_type = type(element).__name__
                    
                    # For tables, convert to markdown format for better readability
                    if element_type == 'Table' and hasattr(element, 'metadata'):
                        if hasattr(element.metadata, 'text_as_html'):
                            # Convert HTML table to markdown-like format
                            element_text = self._html_table_to_markdown(element.metadata.text_as_html)
                    
                    elements_data.append({
                        'text': element_text,
                        'page_number': page_number,
                        'element_type': element_type
                    })
                
                logger.info(f"Extracted {len(elements_data)} elements from {file_type} document")
                
            finally:
                # Clean up temp file
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.error(f"Unstructured extraction failed: {e}")
            # Fallback to basic extraction
            return self._extract_basic(file_content, file_type)
        
        return elements_data

    def _html_table_to_markdown(self, html_table: str) -> str:
        """Convert HTML table to markdown-like format"""
        try:
            from html.parser import HTMLParser
            
            class TableParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.rows = []
                    self.current_row = []
                    self.current_cell = ""
                    self.in_cell = False
                    
                def handle_starttag(self, tag, attrs):
                    if tag in ['td', 'th']:
                        self.in_cell = True
                        self.current_cell = ""
                    elif tag == 'tr':
                        self.current_row = []
                        
                def handle_endtag(self, tag):
                    if tag in ['td', 'th']:
                        self.in_cell = False
                        self.current_row.append(self.current_cell.strip())
                    elif tag == 'tr':
                        if self.current_row:
                            self.rows.append(self.current_row)
                            
                def handle_data(self, data):
                    if self.in_cell:
                        self.current_cell += data
            
            parser = TableParser()
            parser.feed(html_table)
            
            if not parser.rows:
                return html_table
            
            # Convert to markdown table
            lines = []
            for i, row in enumerate(parser.rows):
                lines.append("| " + " | ".join(row) + " |")
                if i == 0:
                    # Add header separator
                    lines.append("| " + " | ".join(["---"] * len(row)) + " |")
            
            return "\n".join(lines)
            
        except Exception as e:
            logger.warning(f"Failed to convert HTML table to markdown: {e}")
            return html_table

    def _extract_basic(self, file_content: bytes, file_type: str) -> List[Dict[str, Any]]:
        """Basic text extraction fallback when Unstructured is not available"""
        try:
            text = ""
            
            if file_type.lower() == 'pdf':
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
                elements = []
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    page_text = page.extract_text()
                    if page_text.strip():
                        elements.append({
                            'text': page_text,
                            'page_number': page_num,
                            'element_type': 'NarrativeText'
                        })
                return elements
                
            elif file_type.lower() in ['docx', 'doc']:
                import docx
                doc = docx.Document(BytesIO(file_content))
                text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                
            elif file_type.lower() in ['txt', 'md']:
                try:
                    text = file_content.decode('utf-8')
                except UnicodeDecodeError:
                    text = file_content.decode('latin-1')
            
            if text.strip():
                return [{
                    'text': text,
                    'page_number': None,
                    'element_type': 'NarrativeText'
                }]
            
            return []
            
        except Exception as e:
            logger.error(f"Basic extraction failed: {e}")
            return []

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

    def _chunk_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk extracted elements while preserving metadata
        
        Returns list of chunks with:
        - text: The chunk text
        - page_number: Original page number
        - element_type: Original element type
        - chunk_index: Index within the document
        """
        chunks = []
        chunk_index = 0
        
        for element in elements:
            element_text = element['text']
            page_number = element.get('page_number')
            element_type = element.get('element_type', 'Unknown')
            
            # Split long elements into chunks
            if len(element_text) > self.text_splitter._chunk_size:
                text_chunks = self.text_splitter.split_text(element_text)
                for text_chunk in text_chunks:
                    chunks.append({
                        'text': text_chunk,
                        'page_number': page_number,
                        'element_type': element_type,
                        'chunk_index': chunk_index
                    })
                    chunk_index += 1
            else:
                chunks.append({
                    'text': element_text,
                    'page_number': page_number,
                    'element_type': element_type,
                    'chunk_index': chunk_index
                })
                chunk_index += 1
        
        return chunks

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
        project_id = doc_data['project_id']

        logger.info(f"Processing document {doc_id}: {doc_data['filename']}")

        # Extract elements using Unstructured
        elements = await asyncio.get_event_loop().run_in_executor(
            self.executor, self._extract_with_unstructured, file_content, doc_data['file_type']
        )

        if not elements:
            logger.warning(f"No content extracted from {doc_data['filename']}")
            return

        # Chunk elements while preserving metadata
        chunks = await asyncio.get_event_loop().run_in_executor(
            self.executor, self._chunk_elements, elements
        )

        logger.info(f"Document {doc_id} split into {len(chunks)} chunks")

        # Get project-specific collection
        collection = self._get_project_collection(project_id)

        # Generate embeddings and store
        documents = []
        metadatas = []
        ids = []
        embeddings = []

        for chunk in chunks:
            # Generate embedding
            embedding = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._generate_embedding, chunk['text']
            )

            chunk_id = self._generate_chunk_id(doc_id, chunk['chunk_index'])

            documents.append(chunk['text'])
            embeddings.append(embedding)
            
            # Create metadata with page number and element type
            metadata = {
                'doc_id': doc_id,
                'project_id': project_id,
                'filename': doc_data['filename'],
                'document_type': doc_data['document_type'],
                'chunk_index': chunk['chunk_index'],
                'total_chunks': len(chunks),
                'element_type': chunk.get('element_type', 'Unknown')
            }

            # Add page number if available
            if chunk.get('page_number') is not None:
                metadata['page_number'] = chunk['page_number']

            # Add affiliation metadata (only non-None values)
            if doc_data.get('equipment_id') is not None:
                metadata['equipment_id'] = doc_data['equipment_id']
            if doc_data.get('sensor_type') is not None:
                metadata['sensor_type'] = doc_data['sensor_type']

            metadatas.append(metadata)
            ids.append(chunk_id)

        # Store in project-specific ChromaDB collection
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

        logger.info(f"Document {doc_id} processed and stored with {len(chunks)} chunks in project collection")

    def _search_with_filter(self, query_embedding: List[float], project_id: str,
                           equipment_id: Optional[str], sensor_type: Optional[str],
                           limit: int) -> List[Dict[str, Any]]:
        """
        Search with specific affiliation filter
        
        Returns results with affiliation_level indicating match type:
        - 'sensor': Matched sensor-specific doc
        - 'equipment': Matched equipment-level doc
        - 'general': Matched general doc
        """
        collection = self._get_project_collection(project_id)
        
        # Build filter based on affiliation
        where_filter = {}
        affiliation_level = 'general'
        
        if equipment_id and sensor_type:
            # Sensor-specific search
            where_filter = {
                "$and": [
                    {"equipment_id": {"$eq": equipment_id}},
                    {"sensor_type": {"$eq": sensor_type}}
                ]
            }
            affiliation_level = 'sensor'
        elif equipment_id:
            # Equipment-level search (no sensor_type)
            where_filter = {
                "$and": [
                    {"equipment_id": {"$eq": equipment_id}},
                    {"sensor_type": {"$exists": False}}
                ]
            }
            affiliation_level = 'equipment'
        else:
            # General search (no equipment_id or sensor_type)
            where_filter = {
                "$and": [
                    {"equipment_id": {"$exists": False}},
                    {"sensor_type": {"$exists": False}}
                ]
            }
            affiliation_level = 'general'
        
        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                where=where_filter if where_filter else None,
                n_results=limit,
                include=['documents', 'metadatas', 'distances']
            )
            
            formatted_results = []
            if results['documents'] and results['metadatas']:
                for doc, metadata, distance in zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                ):
                    # Convert L2 distance to similarity score (0-1 range)
                    similarity = 1 / (1 + distance) if distance >= 0 else 0
                    
                    formatted_results.append({
                        'content': doc,
                        'metadata': metadata,
                        'similarity_score': similarity,
                        'filename': metadata.get('filename'),
                        'equipment_id': metadata.get('equipment_id'),
                        'sensor_type': metadata.get('sensor_type'),
                        'document_type': metadata.get('document_type'),
                        'page_number': metadata.get('page_number'),
                        'element_type': metadata.get('element_type'),
                        'affiliation_level': affiliation_level,
                        'chunk_id': f"{metadata.get('doc_id')}_chunk_{metadata.get('chunk_index')}"
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.warning(f"Search with filter failed: {e}")
            return []

    def _deduplicate_and_rank(self, results: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        """
        Deduplicate results by chunk_id, keeping highest similarity score
        Then rank by: affiliation_level priority + similarity_score
        """
        # Deduplicate by chunk_id, keeping highest similarity
        seen_chunks = {}
        for result in results:
            chunk_id = result.get('chunk_id')
            if chunk_id not in seen_chunks:
                seen_chunks[chunk_id] = result
            elif result['similarity_score'] > seen_chunks[chunk_id]['similarity_score']:
                seen_chunks[chunk_id] = result
        
        unique_results = list(seen_chunks.values())
        
        # Rank by affiliation priority (sensor > equipment > general) then by similarity
        affiliation_priority = {'sensor': 0, 'equipment': 1, 'general': 2}
        
        unique_results.sort(
            key=lambda x: (
                affiliation_priority.get(x.get('affiliation_level', 'general'), 2),
                -x['similarity_score']  # Negative for descending order
            )
        )
        
        return unique_results[:limit]

    async def search_similar(self, query: str, project_id: str,
                           equipment_id: Optional[str] = None,
                           sensor_type: Optional[str] = None,
                           limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar documents using hierarchical affiliation search
        
        Search order (if sensor_type provided):
        1. Sensor-specific docs (equipment_id + sensor_type)
        2. Equipment-level docs (equipment_id only)
        3. General docs (no affiliation)
        
        Results are deduplicated and ranked by affiliation priority + similarity
        """
        try:
            # Generate embedding for query
            query_embedding = await asyncio.get_event_loop().run_in_executor(
                self.executor, self._generate_embedding, query
            )

            all_results = []
            
            # Hierarchical search based on provided filters
            if sensor_type and equipment_id:
                # Level 1: Sensor-specific
                sensor_results = self._search_with_filter(
                    query_embedding, project_id, equipment_id, sensor_type, limit
                )
                all_results.extend(sensor_results)
                
                # Level 2: Equipment-level (if we need more results)
                if len(all_results) < limit:
                    equipment_results = self._search_with_filter(
                        query_embedding, project_id, equipment_id, None, limit
                    )
                    all_results.extend(equipment_results)
                
                # Level 3: General docs (if we still need more)
                if len(all_results) < limit:
                    general_results = self._search_with_filter(
                        query_embedding, project_id, None, None, limit
                    )
                    all_results.extend(general_results)
                    
            elif equipment_id:
                # Level 1: Equipment-level
                equipment_results = self._search_with_filter(
                    query_embedding, project_id, equipment_id, None, limit
                )
                all_results.extend(equipment_results)
                
                # Level 2: General docs
                if len(all_results) < limit:
                    general_results = self._search_with_filter(
                        query_embedding, project_id, None, None, limit
                    )
                    all_results.extend(general_results)
                    
            else:
                # NO FILTERS PROVIDED - Search ALL documents (broad search)
                # This is the recommended approach for most domain knowledge queries
                pass  # Fall through to broad search below
            
            # Broad search: Search ALL documents without any affiliation filter
            # This runs when: no filters provided, OR when filtered search returned no results
            if not all_results:
                collection = self._get_project_collection(project_id)
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit,
                    include=['documents', 'metadatas', 'distances']
                )
                
                if results['documents'] and results['metadatas']:
                    for doc, metadata, distance in zip(
                        results['documents'][0],
                        results['metadatas'][0],
                        results['distances'][0]
                    ):
                        # Determine affiliation level from metadata
                        if metadata.get('sensor_type'):
                            aff_level = 'sensor'
                        elif metadata.get('equipment_id'):
                            aff_level = 'equipment'
                        else:
                            aff_level = 'general'
                            
                        # Convert L2 distance to similarity score (0-1 range)
                        # Using formula: similarity = 1 / (1 + distance)
                        similarity = 1 / (1 + distance) if distance >= 0 else 0
                        
                        all_results.append({
                            'content': doc,
                            'metadata': metadata,
                            'similarity_score': similarity,
                            'filename': metadata.get('filename'),
                            'equipment_id': metadata.get('equipment_id'),
                            'sensor_type': metadata.get('sensor_type'),
                            'document_type': metadata.get('document_type'),
                            'page_number': metadata.get('page_number'),
                            'element_type': metadata.get('element_type'),
                            'affiliation_level': aff_level,
                            'chunk_id': f"{metadata.get('doc_id')}_chunk_{metadata.get('chunk_index')}"
                        })
            
            # Deduplicate and rank results
            return self._deduplicate_and_rank(all_results, limit)

        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return []

    def delete_document(self, project_id: str, doc_id: str) -> bool:
        """Delete all chunks of a document from project collection"""
        try:
            collection = self._get_project_collection(project_id)
            
            # Find all chunks for this document
            results = collection.get(
                where={"doc_id": doc_id},
                include=['metadatas']
            )

            if results['ids']:
                # Delete all chunks
                collection.delete(ids=results['ids'])
                logger.info(f"Deleted document {doc_id} with {len(results['ids'])} chunks")
                return True
            else:
                logger.warning(f"Document {doc_id} not found")
                return False

        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    def get_document_stats(self, project_id: str) -> Dict[str, Any]:
        """Get statistics about stored documents for a project"""
        try:
            collection = self._get_project_collection(project_id)
            
            # Get all documents in collection
            all_results = collection.get(include=['metadatas'])
            metadatas = all_results['metadatas']
            total_chunks = len(all_results['ids'])

            unique_docs = set()
            equipment_docs = set()
            sensor_docs = set()
            file_types = {}
            pages_with_content = set()

            for metadata in metadatas:
                if metadata:
                    doc_id = metadata.get('doc_id')
                    if doc_id:
                        unique_docs.add(doc_id)

                    equipment_id = metadata.get('equipment_id')
                    sensor_type = metadata.get('sensor_type')
                    
                    if sensor_type:
                        sensor_docs.add(f"{doc_id}_{equipment_id}_{sensor_type}")
                    elif equipment_id:
                        equipment_docs.add(f"{doc_id}_{equipment_id}")

                    filename = metadata.get('filename')
                    if filename:
                        ext = Path(filename).suffix[1:].lower()
                        file_types[ext] = file_types.get(ext, 0) + 1
                    
                    page_number = metadata.get('page_number')
                    if page_number:
                        pages_with_content.add(f"{doc_id}_{page_number}")

            return {
                'total_chunks': total_chunks,
                'unique_documents': len(unique_docs),
                'general_documents': len(unique_docs) - len(equipment_docs) - len(sensor_docs),
                'equipment_specific_documents': len(equipment_docs),
                'sensor_specific_documents': len(sensor_docs),
                'file_types': file_types,
                'pages_with_content': len(pages_with_content)
            }

        except Exception as e:
            logger.error(f"Failed to get document stats: {e}")
            return {
                'total_chunks': 0,
                'unique_documents': 0,
                'general_documents': 0,
                'equipment_specific_documents': 0,
                'sensor_specific_documents': 0,
                'file_types': {},
                'pages_with_content': 0
            }

    def clear_project_documents(self, project_id: str) -> int:
        """Delete all documents for a project by deleting the collection"""
        try:
            collection = self._get_project_collection(project_id)
            count = collection.count()
            
            # Delete the entire collection
            self.delete_project_collection(project_id)
            
            logger.info(f"Cleared {count} chunks for project {project_id}")
            return count
        except Exception as e:
            logger.error(f"Failed to clear project documents: {e}")
            return 0

    def list_project_documents(self, project_id: str) -> List[Dict[str, Any]]:
        """List all unique documents in a project with their metadata"""
        try:
            collection = self._get_project_collection(project_id)
            all_results = collection.get(include=['metadatas'])
            
            # Group by doc_id
            docs = {}
            for metadata in all_results['metadatas']:
                if metadata:
                    doc_id = metadata.get('doc_id')
                    if doc_id and doc_id not in docs:
                        docs[doc_id] = {
                            'id': doc_id,
                            'filename': metadata.get('filename'),
                            'document_type': metadata.get('document_type'),
                            'equipment_id': metadata.get('equipment_id'),
                            'sensor_type': metadata.get('sensor_type'),
                            'total_chunks': metadata.get('total_chunks', 0)
                        }
            
            return list(docs.values())
            
        except Exception as e:
            logger.error(f"Failed to list project documents: {e}")
            return []


# Global vector store instance
vector_store = VectorStoreService()
