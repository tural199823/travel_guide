import React, { useEffect, useRef, useState } from 'react';
import { MessageList, Input } from 'react-chat-elements';
import 'react-chat-elements/dist/main.css';
import ReactLoading from 'react-loading';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import ReactMarkdown from 'react-markdown';


const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const socketRef = useRef(null);
  const threadId = "123";
  const [darkMode, setDarkMode] = useState(false);

  // Load saved messages on mount
  useEffect(() => {
    const saved = localStorage.getItem('chatMessages');
    if (saved) {
      setMessages(JSON.parse(saved));
    }
  }, []);

  // Save messages to localStorage on every update
  useEffect(() => {
    if (messages.length === 0) return; 
    localStorage.setItem('chatMessages', JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    const socket = new WebSocket(`ws://localhost:8000/ws/${threadId}`);
    socketRef.current = socket;

    socket.onmessage = (event) => {
        const rawMarkdown = event.data;
        const dirtyHTML = marked.parse(rawMarkdown);
        const cleanHTML = DOMPurify.sanitize(dirtyHTML);

      setMessages((prev) => [
        ...prev,
        {
          position: 'left',
          type: 'html',
          text: cleanHTML,
          title: 'AI',
          avatar: './Images/ai.png',
          date: new Date()
        },
      ]);
      setIsTyping(false); 
    };

    return () => {
      socket.close();
    };
  }, []);

  const sendMessage = () => {
    if (input.trim() === '') return;
    socketRef.current.send(input);
    setMessages((prev) => [
      ...prev,
      {
        position: 'right',
        type: 'text',
        text: input,
        title: 'You',
        avatar: './Images/user.png',
        date: new Date()
      },
    ]);
    setInput('');
    setIsTyping(true);
  };

    return (
        <div
            style={{
            backgroundColor: darkMode ? '#121212' : '#ffffff',
            color: '#e0e0e0',
            height: '100vh',
            display: 'flex',
            flexDirection: 'column',
            fontFamily: 'sans-serif',
            }}
        >
            {/* NavBar */}
            <div
            style={{
                backgroundColor: darkMode ? '#1f1f1f' : '#f0f0f0',
                padding: '1rem 2rem',
                color: darkMode ? 'white' : '#111',
                fontSize: '1.5rem',
                fontWeight: 'bold',
                borderBottom: darkMode ? '1px solid #333' : '1px solid #ccc',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
            }}
            >
            <span>Travel Assistant</span>
            <label className="form-check form-switch">
                <input
                className="form-check-input"
                type="checkbox"
                checked={darkMode}
                onChange={() => setDarkMode(!darkMode)}
                />
                <span
                className="form-check-label"
                style={{ color: darkMode ? '#fff' : '#000' }}
                >
                {darkMode ? 'Dark Mode' : 'Light Mode'}
                </span>
            </label>
            </div>

            {/* Chat Content */}
            <div
            style={{
                maxWidth: 800,
                margin: '2rem auto',
                display: 'flex',
                flexDirection: 'column',
                flex: 1,
            }}
            >
            <div
                style={{
                maxHeight: '80vh',
                overflowY: 'auto',
                marginBottom: '1rem',
                paddingRight: '10px',
                }}
            >
                {messages.map((msg, index) => (
                <div
                    key={index}
                    style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems:
                        msg.position === 'right' ? 'flex-end' : 'flex-start',
                    marginBottom: '1rem',
                    }}
                >
                    <div
                    style={{
                        background:
                        msg.position === 'right'
                            ? darkMode
                            ? '#2a2a2a'
                            : '#d4edda'
                            : darkMode
                            ? '#1e1e1e'
                            : '#f1f0f0',
                        padding: '10px 15px',
                        borderRadius: '10px',
                        maxWidth: '80%',
                        wordBreak: 'break-word',
                        lineHeight: 1.6,
                        textAlign: 'left',
                        color: darkMode ? '#e0e0e0' : '#222',
                    }}
                    >
                    {msg.text.trim().startsWith('<') ? (
                        <div
                        dangerouslySetInnerHTML={{ __html: msg.text }}
                        style={{ lineHeight: 1.6 }}
                        />
                    ) : (
                        <ReactMarkdown
                        children={msg.text}
                        components={{
                            a: ({ node, ...props }) => (
                            <a
                                {...props}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{ color: '#66b2ff' }}
                            />
                            ),
                        }}
                        />
                    )}
                    </div>
                </div>
                ))}

                {/* Typing indicator inside chat */}
                {isTyping && (
                <div
                    style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    marginBottom: '1rem',
                    }}
                >
                    <div
                    style={{
                        backgroundColor: darkMode ? '#1e1e1e' : '#f1f0f0',
                        padding: '10px 15px',
                        borderRadius: '10px',
                        maxWidth: '80%',
                        display: 'flex',
                        alignItems: 'center',
                    }}
                    >
                    <ReactLoading
                        type="bubbles"
                        color={darkMode ? '#888' : '#555'}
                        height={50}
                        width={50}
                    />
                    </div>
                </div>
                )}
            </div>

            {/* Chat input */}
            <div style={{ marginTop: '10px' }}>
                <Input
                className={`form-control ${
                    darkMode ? 'bg-dark text-light border-secondary' : ''
                }`}
                placeholder="Type your message..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => {
                    if (e.key === 'Enter') sendMessage();
                }}
                rightButtons={
                    <button
                    className={`btn ${
                        darkMode ? 'btn-secondary' : 'btn-light'
                    }`}
                    onClick={sendMessage}
                    >
                    Send
                    </button>
                }
                />
            </div>
            </div>
        </div>
        );



};

export default Chat;
