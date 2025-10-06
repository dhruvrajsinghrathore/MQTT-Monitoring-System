import React, { useState, useRef, useEffect } from 'react';
import { X, Send, Bot, User, GripVertical } from 'lucide-react';
import { getApiUrl } from '../config/api';

interface ChatMessage {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
}

interface ChatBotProps {
  isOpen: boolean;
  onClose: () => void;
  context?: string; // Additional context for the chatbot
  pageType?: 'monitor' | 'equipment'; // Page type for context
  cellId?: string; // Cell ID for equipment page
}

const ChatBot: React.FC<ChatBotProps> = ({ isOpen, onClose, context, pageType = 'monitor', cellId }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      text: `Hello! I'm your AI-powered MQTT monitoring assistant. I can help you analyze your cell data, understand sensor readings, and provide insights about your equipment. ${context ? `I can see you're currently viewing ${context}.` : ''} How can I assist you today?`,
      sender: 'bot',
      timestamp: new Date()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [width, setWidth] = useState(Math.floor(window.innerWidth * 0.3)); // Default 30% of screen width
  const [isResizing, setIsResizing] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  const [suggestionStartPos, setSuggestionStartPos] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatBotRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      // Find the messages container (parent with overflow-y-auto)
      const messagesContainer = messagesEndRef.current.closest('.overflow-y-auto');
      if (messagesContainer) {
        // Scroll within the messages container only
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      } else {
        // Fallback: use scrollIntoView with minimal page impact
        messagesEndRef.current.scrollIntoView({ 
          behavior: 'smooth', 
          block: 'end',
          inline: 'nearest'
        });
      }
    }
  };

  const parseReferences = (text: string) => {
    // Parse @ references in the text
    const referenceRegex = /@([a-zA-Z0-9_\s]+)/g;
    const references: string[] = [];
    let match;
    
    while ((match = referenceRegex.exec(text)) !== null) {
      const reference = match[1].trim();
      if (reference && !references.includes(reference)) {
        references.push(reference);
      }
    }
    
    return references;
  };

  const getAvailableSensors = () => {
    // Common sensor names that are typically available
    const commonSensors = [
      'glucose mM', 'pH', 'o2 percent', 'pressure mbar', 'flow uL_min',
      'hcs ROS_AU', 'hcs ROS_IU', 'hcs viability_pct', 'hcs Ca_ratio',
      'aptamer IL6_nM', 'aptamer TNFa_nM', 'barrier impedance_kOhm',
      'qpi cell_count', 'qpi confluence_pct', 'qpi dry_mass_pg',
      'tumor EMT_index', 'tumor prolif_index'
    ];
    
    // If we're on equipment page, we could fetch actual available sensors
    // For now, return common sensors
    return commonSensors;
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInputText(value);
    
    // Check for @ symbol and show suggestions
    const cursorPos = e.target.selectionStart || 0;
    const textBeforeCursor = value.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');
    
    if (lastAtIndex !== -1) {
      const textAfterAt = textBeforeCursor.substring(lastAtIndex + 1);
      const hasSpaceAfterAt = textAfterAt.includes(' ');
      
      if (!hasSpaceAfterAt) {
        // Show suggestions
        const availableSensors = getAvailableSensors();
        const filteredSuggestions = availableSensors.filter(sensor => 
          sensor.toLowerCase().includes(textAfterAt.toLowerCase())
        );
        
        setSuggestions(filteredSuggestions);
        setSuggestionStartPos(lastAtIndex);
        setShowSuggestions(filteredSuggestions.length > 0);
        setSelectedSuggestionIndex(-1);
      } else {
        setShowSuggestions(false);
      }
    } else {
      setShowSuggestions(false);
    }
  };

  const insertSuggestion = (suggestion: string) => {
    const beforeAt = inputText.substring(0, suggestionStartPos);
    const afterCursor = inputText.substring(inputRef.current?.selectionStart || 0);
    const newText = beforeAt + '@' + suggestion + ' ' + afterCursor;
    
    setInputText(newText);
    setShowSuggestions(false);
    
    // Focus back to input
    setTimeout(() => {
      if (inputRef.current) {
        const newCursorPos = beforeAt.length + suggestion.length + 2; // +2 for @ and space
        inputRef.current.focus();
        inputRef.current.setSelectionRange(newCursorPos, newCursorPos);
      }
    }, 0);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (showSuggestions) {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedSuggestionIndex(prev => 
            prev < suggestions.length - 1 ? prev + 1 : prev
          );
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedSuggestionIndex(prev => prev > 0 ? prev - 1 : -1);
          break;
        case 'Enter':
          if (selectedSuggestionIndex >= 0) {
            e.preventDefault();
            insertSuggestion(suggestions[selectedSuggestionIndex]);
          } else if (!e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
          }
          break;
        case 'Escape':
          setShowSuggestions(false);
          break;
      }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatResponse = (text: string, isUserMessage: boolean = false) => {
    // Simple formatting - just split by lines and format based on content
    const lines = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);
    
    return lines.map((line, index) => {
      // Highlight @ references in user messages
      if (isUserMessage && line.includes('@')) {
        const parts = line.split(/(@[a-zA-Z0-9_\s]+)/g);
        return (
          <div key={index} className={`mb-1 ${isUserMessage ? 'text-white' : 'text-gray-700'}`}>
            {parts.map((part, partIndex) => {
              if (part.startsWith('@')) {
                return (
                  <span key={partIndex} className="bg-blue-600 text-white px-1 rounded text-sm font-medium">
                    {part}
                  </span>
                );
              }
              return part;
            })}
          </div>
        );
      }
      
      // Main headings (ALL CAPS ending with colon)
      if (line.match(/^[A-Z][A-Z\s]+:$/)) {
        return (
          <div key={index} className={`font-bold mt-4 mb-2 text-lg ${isUserMessage ? 'text-white' : 'text-gray-900'}`}>
            {line}
          </div>
        );
      }
      // Cell names (CELL followed by number)
      else if (line.match(/^CELL\d+:/)) {
        return (
          <div key={index} className={`font-semibold mt-3 mb-2 text-base ${isUserMessage ? 'text-white' : 'text-gray-900'}`}>
            {line}
          </div>
        );
      }
      // Property headings (Title Case ending with colon)
      else if (line.match(/^[A-Z][a-z\s]+:$/)) {
        return (
          <div key={index} className={`font-medium mt-2 mb-1 ${isUserMessage ? 'text-white' : 'text-gray-700'}`}>
            {line}
          </div>
        );
      }
      // Sensor readings (contains colon and parentheses)
      else if (line.includes(':') && line.includes('(') && line.includes(')')) {
        return (
          <div key={index} className={`ml-4 mb-1 ${isUserMessage ? 'text-white' : 'text-gray-600'}`}>
            • {line}
          </div>
        );
      }
      // Regular text
      else {
        return (
          <div key={index} className={`mb-1 ${isUserMessage ? 'text-white' : 'text-gray-700'}`}>
            {line}
          </div>
        );
      }
    });
  };

  useEffect(() => {
    // Only scroll to bottom if there are messages and the chatbot is open
    if (messages.length > 0 && isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  // Handle mouse events for resizing
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      
      const newWidth = window.innerWidth - e.clientX;
      const minWidth = 400; // Increased minimum width for better readability
      const maxWidth = window.innerWidth * 0.8; // Maximum 80% of screen width
      
      if (newWidth >= minWidth && newWidth <= maxWidth) {
        setWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  const handleSendMessage = async () => {
    if (!inputText.trim()) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: inputText,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    const currentQuery = inputText;
    setInputText('');
    setIsTyping(true);

    try {
      // Parse @ references from the user query
      const references = parseReferences(currentQuery);
      
      // Call backend LLM service
      const response = await fetch(getApiUrl('/api/chatbot/query'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: currentQuery,
          page_type: pageType,
          cell_id: cellId,
          references: references // Send parsed references to backend
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      
      const botMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        text: data.response,
        sender: 'bot',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error('Error calling LLM service:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        text: `I apologize, but I encountered an error processing your query. Please try again or check if the backend service is running. Error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        sender: 'bot',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };


  if (!isOpen) return null;

  return (
    <div 
      ref={chatBotRef}
      className="bg-white shadow-xl border-l border-gray-200 flex flex-col h-screen relative"
      style={{ width: `${width}px` }}
    >
      {/* Resize handle */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1 bg-gray-300 hover:bg-blue-500 cursor-col-resize z-10"
        onMouseDown={() => setIsResizing(true)}
      >
        <div className="absolute left-0 top-1/2 transform -translate-y-1/2 w-1 h-8 bg-gray-400 hover:bg-blue-500 rounded-r"></div>
      </div>
      {/* Header */}
      <div className="bg-blue-600 text-white p-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center space-x-2">
          <Bot className="w-5 h-5" />
          <h3 className="font-semibold">AI MQTT Assistant</h3>
        </div>
        <button
          onClick={onClose}
          className="text-white hover:text-gray-200 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Messages - Fixed height with scroll */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`px-4 py-2 rounded-lg ${
                message.sender === 'user'
                  ? 'bg-blue-500'
                  : 'bg-white text-gray-800 border border-gray-200'
              }`}
              style={{
                maxWidth: `${Math.min(width - 80, 600)}px`, // Responsive max width
                minWidth: '200px', // Minimum width for readability
                color: message.sender === 'user' ? '#ffffff' : undefined // Force white text for user messages
              }}
            >
              <div className="flex items-start space-x-2">
                {message.sender === 'bot' && (
                  <Bot className="w-4 h-4 mt-0.5 flex-shrink-0" />
                )}
                {message.sender === 'user' && (
                  <User className="w-4 h-4 mt-0.5 flex-shrink-0" />
                )}
                <div className="flex-1">
                  <div 
                    className="text-base whitespace-pre-wrap break-words leading-relaxed"
                    style={{ color: message.sender === 'user' ? '#ffffff' : undefined }}
                  >
                    {formatResponse(message.text, message.sender === 'user')}
                  </div>
                  <p 
                    className="text-xs opacity-70 mt-2"
                    style={{ color: message.sender === 'user' ? '#ffffff' : undefined }}
                  >
                    {message.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        ))}
        
        {isTyping && (
          <div className="flex justify-start">
            <div 
              className="bg-gray-100 text-gray-900 px-4 py-2 rounded-lg"
              style={{
                maxWidth: `${Math.min(width - 80, 600)}px`,
                minWidth: '200px'
              }}
            >
              <div className="flex items-center space-x-2">
                <Bot className="w-4 h-4" />
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input - Fixed at bottom */}
      <div className="border-t border-gray-200 p-4 flex-shrink-0 relative">
        <div className="flex space-x-2">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={inputText}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Ask me about your cell data..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={isTyping}
            />
            
            {/* Suggestions Dropdown */}
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute bottom-full left-0 right-0 mb-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto z-50">
                {suggestions.map((suggestion, index) => (
                  <div
                    key={suggestion}
                    className={`px-3 py-2 cursor-pointer text-sm ${
                      index === selectedSuggestionIndex
                        ? 'bg-blue-100 text-blue-800'
                        : 'hover:bg-gray-100'
                    }`}
                    onClick={() => insertSuggestion(suggestion)}
                  >
                    <span className="text-blue-600 font-medium">@</span>
                    {suggestion}
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={handleSendMessage}
            disabled={!inputText.trim() || isTyping}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg flex items-center space-x-2 transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatBot;