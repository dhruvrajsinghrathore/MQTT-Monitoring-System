import React, { useState, useRef, useEffect } from 'react';
import { X, Send, Bot, User } from 'lucide-react';

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
}

const ChatBot: React.FC<ChatBotProps> = ({ isOpen, onClose }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      text: `Hello! I'm your MQTT monitoring assistant. I can help you with questions about your equipment, sensor data, and system status. How can I assist you today?`,
      sender: 'bot',
      timestamp: new Date()
    }
  ]);
  const [inputText, setInputText] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputText.trim()) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: inputText,
      sender: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsTyping(true);

    // Simulate bot response (in a real implementation, this would call an API)
    setTimeout(() => {
      const botResponse = generateBotResponse(inputText);
      const botMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        text: botResponse,
        sender: 'bot',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, botMessage]);
      setIsTyping(false);
    }, 1000 + Math.random() * 1000); // Random delay between 1-2 seconds
  };

  const generateBotResponse = (userInput: string): string => {
    const input = userInput.toLowerCase();
    
    // Equipment-related responses
    if (input.includes('equipment') || input.includes('cell')) {
      return "I can help you understand your equipment status. Each cell in your system monitors different sensors like temperature, pressure, and flow rates. You can click on any cell in the monitoring view to see detailed sensor data and trends.";
    }
    
    // Sensor-related responses
    if (input.includes('sensor') || input.includes('data')) {
      return "Your sensors are collecting real-time data including temperature, pressure, flow rates, and composition measurements. The data is displayed in both the monitoring dashboard and detailed equipment views. You can also view historical data trends over time.";
    }
    
    // Connection-related responses
    if (input.includes('connection') || input.includes('connect') || input.includes('disconnect')) {
      return "The connection status shows whether your system is successfully communicating with the MQTT broker. Green means connected, red means there's an issue. Make sure your MQTT broker is running and accessible.";
    }
    
    // Monitoring-related responses
    if (input.includes('monitor') || input.includes('start') || input.includes('stop')) {
      return "You can start and stop monitoring using the controls in the header. When monitoring is active, you'll see real-time updates from your equipment. The recording feature lets you save data sessions for later analysis.";
    }
    
    // Chart-related responses
    if (input.includes('chart') || input.includes('graph') || input.includes('trend')) {
      return "The charts show sensor data trends over time. You can select which sensor types to display using the feature selection buttons. The charts update in real-time as new data arrives from your equipment.";
    }
    
    // General help
    if (input.includes('help') || input.includes('how')) {
      return "I can help you with:\n• Understanding your equipment and sensors\n• Interpreting connection status\n• Explaining monitoring controls\n• Reading charts and trends\n• Troubleshooting issues\n\nWhat specific topic would you like to know more about?";
    }
    
    // Default response
    return "I understand you're asking about: \"" + userInput + "\". I'm here to help with your MQTT monitoring system. You can ask me about equipment status, sensor data, connection issues, or how to use the monitoring features. What would you like to know more about?";
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="w-96 bg-white shadow-xl border-l border-gray-200 flex flex-col h-screen">
      {/* Header */}
      <div className="bg-blue-600 text-white p-4 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center space-x-2">
          <Bot className="w-5 h-5" />
          <h3 className="font-semibold">MQTT Assistant</h3>
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
              className={`max-w-xs px-4 py-2 rounded-lg ${
                message.sender === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-900'
              }`}
            >
              <div className="flex items-start space-x-2">
                {message.sender === 'bot' && (
                  <Bot className="w-4 h-4 mt-0.5 flex-shrink-0" />
                )}
                {message.sender === 'user' && (
                  <User className="w-4 h-4 mt-0.5 flex-shrink-0" />
                )}
                <div className="flex-1">
                  <p className="text-sm whitespace-pre-wrap">{message.text}</p>
                  <p className="text-xs opacity-70 mt-1">
                    {message.timestamp.toLocaleTimeString()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        ))}
        
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-gray-100 text-gray-900 px-4 py-2 rounded-lg">
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
      <div className="border-t border-gray-200 p-4 flex-shrink-0">
        <div className="flex space-x-2">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask me about your MQTT system..."
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isTyping}
          />
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
