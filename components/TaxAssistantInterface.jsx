import React, { useState, useRef, useEffect } from 'react';
import { Card, CardBody, Button, Input, Row, Col, ListGroup, ListGroupItem } from 'reactstrap';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github.css';

const TaxAssistantInterface = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [removingDocId, setRemovingDocId] = useState(null);
  const [debugInfo, setDebugInfo] = useState('');
  const [showDebug, setShowDebug] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  const userId = 'test-user-123';
  const BACKEND_URL =
    process.env.NEXT_PUBLIC_BACKEND_URL || process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

  const defaultRecent = [
    'Recent conversations will appear here',
    'Click + to start a new chat',
    'Upload documents for analysis'
  ];

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    loadInitialConversations();
  }, []);

  useEffect(() => {
    if (!activeConversationId) return;
    fetchConversationHistory(activeConversationId);
    fetchConversationDocuments(activeConversationId);
  }, [activeConversationId]);

  function addDebugInfo(message) {
    const timestamp = new Date().toLocaleTimeString();
    setDebugInfo(prev => `[${timestamp}] ${message}\n${prev}`);
  }

  // Interactive markdown helpers (hoisted so they are available during render)
  const slugify = txt =>
    String(txt || '')
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .trim()
      .replace(/\s+/g, '-');

  const HeadingTag =
    level =>
    ({ children }) => {
      const text = Array.isArray(children)
        ? children.map(c => (typeof c === 'string' ? c : '')).join('')
        : String(children || '');
      const id = slugify(text);
      const Tag = `h${level}`;
      return (
        <Tag id={id} style={{ scrollMarginTop: '72px' }}>
          <a href={`#${id}`} aria-label="Anchor link" style={{ textDecoration: 'none', color: 'inherit' }}>
            🔗
          </a>{' '}
          {children}
        </Tag>
      );
    };

  const HeadingH2 = HeadingTag(2);
  const HeadingH3 = HeadingTag(3);

  const CodeBlock = ({ inline, className, children, ...props }) => {
    const [copied, setCopied] = React.useState(false);
    const code = String(children || '').replace(/\n$/, '');
    if (inline) {
      return (
        <code className={className} {...props}>
          {code}
        </code>
      );
    }
    const onCopy = async () => {
      try {
        await navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      } catch (e) {
        // ignore
      }
    };
    return (
      <div className="code-block" style={{ position: 'relative' }}>
        <button
          type="button"
          className="copy-btn"
          onClick={onCopy}
          aria-label="Copy code"
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            padding: '4px 8px',
            fontSize: 12,
            border: '1px solid #d0d7de',
            borderRadius: 6,
            background: copied ? '#e6ffed' : '#f6f8fa',
            cursor: 'pointer'
          }}>
          {copied ? 'Copied' : 'Copy'}
        </button>
        <pre className={className} {...props}>
          <code>{code}</code>
        </pre>
      </div>
    );
  };

  function renderAssistantContent(content) {
    return (
      <div className="assistant-markdown">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeHighlight]}
          components={{
            a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
            table: ({ node, ...props }) => (
              <div style={{ overflowX: 'auto' }}>
                <table {...props} />
              </div>
            ),
            code: CodeBlock,
            h2: HeadingH2,
            h3: HeadingH3
          }}>
          {content || ''}
        </ReactMarkdown>
      </div>
    );
  }

  // Load existing conversations, then select latest or create a new one
  async function loadInitialConversations() {
    addDebugInfo('🔵 Loading conversations');
    setIsLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/conversation/list?user_id=${userId}`);
      if (res.ok) {
        const data = await res.json();
        const items = (data?.conversations || []).slice().reverse(); // newest first
        setConversations(
          items.map(item => ({
            id: item.id,
            title: String(item.id) // Show chat ID instead of "New Conversation"
          }))
        );
        if (items.length > 0) {
          setActiveConversationId(items[0].id);
        } else {
          await handleNewConversation();
        }
      } else {
        addDebugInfo(`❌ list conversations failed: HTTP ${res.status}`);
        await handleNewConversation();
      }
    } catch (e) {
      addDebugInfo(`❌ list conversations error: ${e.message}`);
      await handleNewConversation();
    } finally {
      setIsLoading(false);
    }
  }

  async function fetchConversationHistory(conversationId) {
    try {
      addDebugInfo(`🔵 Loading history for ${conversationId}`);
      const res = await fetch(`${BACKEND_URL}/conversation/history/${conversationId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setMessages(data?.messages || []);
    } catch (e) {
      addDebugInfo(`❌ Failed to load history: ${e.message}`);
      setMessages([]);
    }
  }

  async function fetchConversationDocuments(conversationId) {
    try {
      addDebugInfo(`🔵 Loading documents for ${conversationId}`);
      const res = await fetch(`${BACKEND_URL}/conversation/${conversationId}/documents`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const docs = data?.documents || [];
      setUploadedDocs(
        docs.map(d => ({
          id: d.id,
          filename: d.filename || (d.metadata && d.metadata.title) || 'Untitled',
          document_type: d.document_type,
          linked_to_conversation: true
        }))
      );
    } catch (e) {
      addDebugInfo(`❌ Failed to load documents: ${e.message}`);
      setUploadedDocs([]);
    }
  }

  async function handleNewConversation() {
    addDebugInfo('🔵 Creating new conversation');
    setIsLoading(true);

    try {
      const response = await fetch(`${BACKEND_URL}/conversation/new`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData?.detail || `HTTP ${response.status}`);
      }

      const data = await response.json();
      const newConvId = data.conversation_id;

      addDebugInfo(`✅ New conversation created: ${newConvId}`);

      setActiveConversationId(newConvId);
      setMessages([]);
      setInput('');

      setConversations(prev => {
        const updated = [{ id: newConvId, title: String(newConvId), messages: [] }, ...prev];
        return updated.slice(0, 10);
      });
    } catch (e) {
      console.error('Failed to create conversation:', e);
      addDebugInfo(`❌ Failed to create conversation: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDeleteConversation(convId) {
    try {
      addDebugInfo(`🔵 Deleting conversation ${convId}`);
      const res = await fetch(`${BACKEND_URL}/conversation/${convId}`, {
        method: 'DELETE'
      });
      let data = {};
      try {
        data = await res.json();
      } catch {
        // ignore non-json
      }
      if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }
      addDebugInfo(`✅ Conversation ${convId} deleted`);
    } catch (e) {
      addDebugInfo(`❌ Failed to delete conversation: ${e.message} (removing locally)`);
    } finally {
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (activeConversationId === convId) {
        const remaining = conversations.filter(c => c.id !== convId);
        if (remaining.length > 0) {
          setActiveConversationId(remaining[0].id);
        } else {
          await handleNewConversation();
        }
        setMessages([]);
      }
    }
  }

  async function handleSend() {
    if (!input.trim() || sending || streaming || !activeConversationId) return;

    const userMsg = {
      id: `user-${Date.now()}`,
      conversation_id: activeConversationId,
      role: 'user',
      content: input.trim(),
      created_at: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setSending(true);
    setStreaming(true);

    let currentText = '';

    function upsertAssistantContent(newContent) {
      setMessages(prev => {
        const copy = [...prev];
        if (copy.length === 0 || copy[copy.length - 1].role !== 'assistant') {
          copy.push({
            id: `assistant-${Date.now()}`,
            conversation_id: activeConversationId,
            role: 'assistant',
            content: '',
            created_at: new Date().toISOString()
          });
        }
        const idx = copy.length - 1;
        copy[idx] = { ...copy[idx], content: newContent };
        return copy;
      });
    }

    /* moved markdown helpers and renderAssistantContent above so they're in scope during render */

    addDebugInfo('🔵 Sending message...');

    try {
      const response = await fetch(`${BACKEND_URL}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: input.trim(),
          conversation_id: activeConversationId,
          user_id: userId
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData?.detail || `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n').filter(Boolean);

        for (const line of lines) {
          if (!line.trim()) continue;
          if (!line.startsWith('data: ')) continue;

          const jsonStr = line.slice(6);
          if (jsonStr === '[DONE]') {
            setStreaming(false);
            continue;
          }

          try {
            const evt = JSON.parse(jsonStr);
            handleStreamEvent(evt);
          } catch (parseErr) {
            console.warn('Failed to parse SSE JSON:', parseErr);
          }
        }
      }

      function handleStreamEvent(evt) {
        if (evt?.type === 'content') {
          currentText = (currentText || '') + (evt.text || '');
          upsertAssistantContent(currentText);
        } else if (evt?.type === 'final') {
          const strategy = (evt?.metadata && evt.metadata.synthesis_method) || evt.synthesis_method || null;
          if (strategy) {
            addDebugInfo(`🧠 Synthesis strategy: ${strategy}`);
          }
          const finalText = evt.answer || currentText || '';
          const displayText = strategy ? `${finalText}\n\n[Strategy: ${strategy}]` : finalText;
          upsertAssistantContent(displayText);
        } else if (evt?.type === 'error') {
          console.error('Stream error:', evt.message);
          addDebugInfo(`❌ Stream error: ${evt.message}`);
        }
      }
      addDebugInfo('✅ Message sent successfully');
    } catch (e) {
      console.error('Send failed', e);
      addDebugInfo(`❌ Send failed: ${e.message}`);
    } finally {
      setSending(false);
      setStreaming(false);
    }
  }

  async function handleUpload(file) {
    addDebugInfo('🔵 handleUpload called');
    addDebugInfo(`File: ${file?.name} (${file?.size} bytes)`);
    addDebugInfo(`User ID: ${userId}`);
    addDebugInfo(`Active Conversation: ${activeConversationId}`);
    addDebugInfo(`Backend URL: ${BACKEND_URL}`);

    if (!file) {
      addDebugInfo('❌ No file provided');
      alert('No file selected!');
      return;
    }

    if (!activeConversationId) {
      addDebugInfo('❌ No active conversation ID');
      alert('No active conversation! Please create a new conversation first by clicking the + button.');
      return;
    }

    if (!BACKEND_URL) {
      addDebugInfo('❌ No BACKEND_URL defined');
      alert('Backend URL not configured!');
      return;
    }

    setUploading(true);
    addDebugInfo('🔵 Starting upload...');

    try {
      const form = new FormData();
      form.append('file', file);
      form.append('metadata', JSON.stringify({ uploaded_via: 'ui', size: file.size }));
      form.append('conversation_id', activeConversationId);
      form.append('user_id', userId);

      addDebugInfo('🔵 FormData created, sending request...');

      const res = await fetch(`${BACKEND_URL}/upload/document`, {
        method: 'POST',
        body: form
      });

      addDebugInfo(`🔵 Response status: ${res.status}`);

      const data = await res.json();
      addDebugInfo(`🔵 Response data: ${JSON.stringify(data)}`);

      if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}: ${data?.message || 'Unknown error'}`);
      }

      addDebugInfo('✅ Upload successful!');

      // Refresh documents from backend to show all linked documents
      await fetchConversationDocuments(activeConversationId);

      // Add success message to chat
      const ack = {
        id: `sys-${Date.now()}`,
        conversation_id: activeConversationId,
        role: 'assistant',
        content: `✅ Document "${file.name}" uploaded successfully! Processing complete. You can now ask questions about it.`,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, ack]);
    } catch (e) {
      addDebugInfo(`❌ Upload failed: ${e.message}`);
      console.error('Upload error:', e);

      // Add error message to chat
      const err = {
        id: `err-${Date.now()}`,
        conversation_id: activeConversationId,
        role: 'assistant',
        content: `❌ Upload failed: ${e.message}`,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, err]);
    } finally {
      setUploading(false);
      addDebugInfo('🔵 Upload process finished');
    }
  }

  function onDropZoneClick(e) {
    e.preventDefault();
    e.stopPropagation();
    addDebugInfo('🔵 Upload button clicked');
    addDebugInfo(`🔵 fileInputRef.current: ${fileInputRef.current}`);

    if (!fileInputRef.current) {
      addDebugInfo('❌ File input ref is null!');
      alert('File input not found! Please refresh the page.');
      return;
    }

    try {
      fileInputRef.current.click();
      addDebugInfo('🔵 File dialog triggered');
    } catch (error) {
      addDebugInfo(`❌ Error clicking file input: ${error.message}`);
    }
  }

  function onFileChange(e) {
    addDebugInfo('🔵 onFileChange called');
    addDebugInfo(`Files selected: ${e.target.files?.length || 0}`);

    const file = e.target.files?.[0];
    if (file) {
      addDebugInfo(`Selected file: ${file.name} (${file.type}, ${file.size} bytes)`);

      // Validate file type
      const allowedTypes = ['.pdf', '.doc', '.docx', '.txt'];
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();

      if (!allowedTypes.includes(fileExtension)) {
        addDebugInfo(`❌ Invalid file type: ${fileExtension}`);
        alert(`File type not supported. Please upload: ${allowedTypes.join(', ')}`);
        e.target.value = ''; // Reset
        return;
      }

      handleUpload(file);
    } else {
      addDebugInfo('❌ No file in selection');
    }

    // Reset input so same file can be selected again
    e.target.value = '';
  }

  function onDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    addDebugInfo('🔵 File dropped');

    const file = e.dataTransfer?.files?.[0];
    if (file) {
      addDebugInfo(`Dropped file: ${file.name}`);
      handleUpload(file);
    }
  }

  function onDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  async function handleRemoveDoc(doc) {
    if (!doc?.id || !activeConversationId) return;
    setRemovingDocId(doc.id);
    try {
      // Use legacy-compatible endpoint; backend also supports /api/chat/{id}/documents/{docId}
      const res = await fetch(`${BACKEND_URL}/conversation/${activeConversationId}/document/${doc.id}`, {
        method: 'DELETE'
      });
      let data = {};
      try {
        data = await res.json();
      } catch {
        // ignore non-json
      }
      if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }

      // Update local state
      setUploadedDocs(prev => prev.filter(d => d.id !== doc.id));

      // Acknowledge in chat
      const ack = {
        id: `sys-${Date.now()}`,
        conversation_id: activeConversationId,
        role: 'assistant',
        content: `🗑️ Removed document "${doc.filename}" from this conversation.`,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, ack]);
      addDebugInfo(`✅ Unlinked document ${doc.id} (${doc.filename})`);
    } catch (e) {
      console.error('Remove document failed:', e);
      addDebugInfo(`❌ Remove document failed: ${e.message}`);
      const err = {
        id: `err-${Date.now()}`,
        conversation_id: activeConversationId,
        role: 'assistant',
        content: `❌ Failed to remove document: ${e.message}`,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, err]);
    } finally {
      setRemovingDocId(null);
    }
  }

  async function handleClearHistory() {
    if (!activeConversationId) return;
    try {
      if (typeof window !== 'undefined') {
        const ok = window.confirm('Clear all messages in this conversation? This cannot be undone.');
        if (!ok) return;
      }
      addDebugInfo(`🔵 Clearing history for ${activeConversationId}`);
      const res = await fetch(`${BACKEND_URL}/conversation/${activeConversationId}/history`, { method: 'DELETE' });
      let data = {};
      try {
        data = await res.json();
      } catch {
        // ignore non-json
      }
      if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }
      setMessages([]);
      addDebugInfo(`✅ History cleared for ${activeConversationId}`);
    } catch (e) {
      addDebugInfo(`❌ Failed to clear history: ${e.message}`);
    }
  }

  const isDisabled = sending || streaming || isLoading;

  return (
    <div className="tax-ui container-fluid" data-testid="tax-interface">
      <Row>
        {/* Sidebar */}
        <Col md="3" lg="3" className="tax-sidebar">
          <div className="sidebar-section">
            <div className="d-flex justify-content-between align-items-center mb-2">
              <h6 className="mb-0">Recent Chats</h6>
              <Button
                size="sm"
                color="light"
                className="px-2 py-1"
                onClick={handleNewConversation}
                disabled={isDisabled}>
                +
              </Button>
            </div>
            <ListGroup flush className="tax-recent-chats" data-testid="recent-chats">
              {conversations.length === 0
                ? defaultRecent.map((title, idx) => (
                    <ListGroupItem key={idx} className={idx === 0 ? 'active' : ''}>
                      {title}
                    </ListGroupItem>
                  ))
                : conversations.map(c => (
                    <ListGroupItem
                      key={c.id}
                      className={c.id === activeConversationId ? 'active cursor-pointer' : 'cursor-pointer'}
                      onClick={() => setActiveConversationId(c.id)}
                      style={{ cursor: 'pointer' }}>
                      {c.title}
                      {conversations.length > 1 && (
                        <Button
                          size="sm"
                          color="link"
                          className="float-right p-0"
                          onClick={e => {
                            e.stopPropagation();
                            handleDeleteConversation(c.id);
                          }}>
                          ×
                        </Button>
                      )}
                    </ListGroupItem>
                  ))}
            </ListGroup>
          </div>

          {/* Uploaded Documents */}
          <div className="sidebar-section mt-3">
            <h6 className="mb-2">Documents ({uploadedDocs.length})</h6>
            <ul className="list-unstyled small">
              {uploadedDocs.length === 0 ? (
                <li className="text-muted">No documents uploaded yet</li>
              ) : (
                uploadedDocs.map(doc => (
                  <li key={doc.id} className="mb-1">
                    📄 {doc.filename}
                    <Button
                      size="sm"
                      color="link"
                      className="p-0 ml-2 text-danger"
                      title="Remove document from this conversation"
                      onClick={() => handleRemoveDoc(doc)}
                      disabled={removingDocId === doc.id || isDisabled}>
                      {removingDocId === doc.id ? '…' : '×'}
                    </Button>
                  </li>
                ))
              )}
            </ul>
          </div>
        </Col>

        {/* Main Chat Area */}
        <Col md="9" lg="9" className="tax-chat">
          {/* Debug Panel - Toggle */}
          {process.env.NODE_ENV === 'development' && (
            <div className="mb-2">
              <Button size="sm" color="secondary" onClick={() => setShowDebug(!showDebug)}>
                {showDebug ? 'Hide' : 'Show'} Debug Info
              </Button>
            </div>
          )}

          {/* Debug Panel */}
          {showDebug && process.env.NODE_ENV === 'development' && (
            <Card className="mb-3" style={{ backgroundColor: '#f8f9fa' }}>
              <CardBody>
                <h6>Debug Information</h6>
                <div className="small">
                  <div>
                    Backend URL: <strong>{BACKEND_URL}</strong>
                  </div>
                  <div>
                    Active Conversation: <strong>{activeConversationId || 'None'}</strong>
                  </div>
                  <div>
                    User ID: <strong>{userId}</strong>
                  </div>
                  <div>
                    Uploading: <strong>{uploading ? 'Yes' : 'No'}</strong>
                  </div>
                  <div>
                    File Input Ref: <strong>{fileInputRef.current ? 'Connected' : 'NULL'}</strong>
                  </div>
                  <div>
                    Loading: <strong>{isLoading ? 'Yes' : 'No'}</strong>
                  </div>
                </div>

                {/* Test Buttons */}
                <div className="mt-2">
                  <Button size="sm" color="info" onClick={() => addDebugInfo('Manual test message')}>
                    Test Debug Log
                  </Button>
                  <Button size="sm" color="warning" className="ml-2" onClick={() => setDebugInfo('')}>
                    Clear Log
                  </Button>
                  <Button size="sm" color="primary" className="ml-2" onClick={onDropZoneClick}>
                    Test File Click
                  </Button>
                </div>

                {/* Debug Log */}
                <pre
                  style={{
                    height: '150px',
                    overflow: 'auto',
                    backgroundColor: '#f8f9fa',
                    padding: '10px',
                    marginTop: '10px',
                    fontSize: '11px',
                    border: '1px solid #dee2e6'
                  }}>
                  {debugInfo || 'No debug messages yet...'}
                </pre>
              </CardBody>
            </Card>
          )}

          {/* Welcome */}
          {messages.length === 0 && (
            <Card className="mb-3" data-testid="welcome-card">
              <CardBody>
                <div className="text-muted mb-2">AI Tax Assistant</div>
                <p className="mb-0">
                  Hello! I'm your M&A Tax Intelligence Assistant. I can help you with complex tax queries by analyzing
                  regulations, case law, precedents, and expert knowledge. Feel free to ask questions or upload relevant
                  documents using the 📎 button.
                </p>
              </CardBody>
            </Card>
          )}

          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.doc,.docx,.txt"
            onChange={onFileChange}
            style={{ display: 'none' }}
          />

          {/* Conversation toolbar */}
          <div className="d-flex justify-content-between align-items-center mb-2">
            <div className="small text-muted">
              Conversation ID: <code>{activeConversationId || 'None'}</code>
            </div>
            <div>
              <Button
                size="sm"
                color="warning"
                className="mr-2"
                onClick={handleClearHistory}
                disabled={isDisabled || !activeConversationId}>
                Clear History
              </Button>
              <Button
                size="sm"
                color="danger"
                onClick={() => handleDeleteConversation(activeConversationId)}
                disabled={isDisabled || !activeConversationId}>
                Delete Chat
              </Button>
            </div>
          </div>

          {/* Messages */}
          <div
            className="mb-3"
            style={{ minHeight: 240, maxHeight: 420, overflowY: 'auto', padding: '0 6px' }}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragEnter={e => e.preventDefault()}
            onDragLeave={e => e.preventDefault()}>
            {messages.map(m => (
              <div
                key={m.id}
                className={`mb-2 p-2 rounded ${m.role === 'user' ? 'bg-primary text-white' : 'bg-light'}`}
                style={{ maxWidth: '85%', marginLeft: m.role === 'user' ? 'auto' : '0' }}>
                <div className="small text-muted mb-1">{m.role === 'user' ? 'You' : 'Assistant'}</div>
                {m.role === 'assistant' ? (
                  renderAssistantContent(m.content)
                ) : (
                  <div style={{ whiteSpace: 'pre-wrap' }}>{m.content}</div>
                )}
              </div>
            ))}
            {streaming && (
              <div className="mb-2 p-2 rounded bg-light">
                <div className="small text-muted mb-1">Assistant</div>
                <div className="text-muted">Typing...</div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="tax-input d-flex align-items-center">
            {/* Small upload icon button */}
            <Button
              color="outline-secondary"
              size="sm"
              className="mr-2"
              onClick={onDropZoneClick}
              disabled={uploading || isDisabled}
              title="Upload document (PDF, DOC, DOCX, TXT)"
              style={{
                padding: '0.375rem 0.5rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                minWidth: '38px'
              }}>
              {uploading ? '⏳' : '📎'}
            </Button>

            <Input
              type="text"
              placeholder="Ask about M&A tax matters, upload documents for analysis, or start a new topic..."
              className="mr-2"
              data-testid="chat-input"
              value={input}
              disabled={isDisabled || !activeConversationId}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
            />
            <Button
              color="primary"
              data-testid="send-button"
              disabled={isDisabled || !activeConversationId}
              onClick={handleSend}>
              {sending || streaming ? 'Sending...' : 'Send'}
            </Button>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default TaxAssistantInterface;
