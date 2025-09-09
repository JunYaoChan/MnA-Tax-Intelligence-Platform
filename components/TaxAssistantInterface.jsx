'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Row, Col, Card, CardBody, ListGroup, ListGroupItem, Button, Input } from 'reactstrap';
import useAuthUser from '../lib/useAuthUser';
import { BACKEND_URL, getJSON, postJSON, postStream } from '../lib/apiClient';

const defaultRecent = ['IRC Section 368 Analysis', 'Cross-border Merger Struct...', 'Tax-free Reorganization Rules'];

const TaxAssistantInterface = () => {
  const { user, isLoading } = useAuthUser();
  const userId = useMemo(() => user?.sub || user?.user_id || 'demo-user', [user]);

  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadedDocs, setUploadedDocs] = useState([]);
  const [debugInfo, setDebugInfo] = useState('');

  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  // Debug helper
  const addDebugInfo = message => {
    console.log(message);
    setDebugInfo(prev => prev + '\n' + new Date().toLocaleTimeString() + ': ' + message);
  };

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streaming]);

  // Load or create conversation on user ready
  useEffect(() => {
    if (!userId || isLoading) return;
    (async () => {
      try {
        addDebugInfo('🔵 Loading conversations...');
        // Fetch list
        const res = await getJSON(`/api/chat/list?user_id=${encodeURIComponent(userId)}`);
        const convs = res?.conversations || [];
        setConversations(convs);
        addDebugInfo(`🔵 Found ${convs.length} conversations`);

        if (convs.length > 0) {
          setActiveConversationId(convs[0].id);
          addDebugInfo(`🔵 Set active conversation: ${convs[0].id}`);
        } else {
          // Create if none
          addDebugInfo('🔵 No conversations found, creating new one...');
          const created = await postJSON('/api/chat/new', {
            user_id: userId,
            title: 'New Conversation'
          });
          const convId = created?.conversation_id;
          if (convId) {
            setConversations([{ id: convId, title: created?.title || 'New Conversation' }]);
            setActiveConversationId(convId);
            addDebugInfo(`🔵 Created new conversation: ${convId}`);
          }
        }
      } catch (e) {
        console.error('Failed to load conversations', e);
        addDebugInfo(`❌ Failed to load conversations: ${e.message}`);
      }
    })();
  }, [userId, isLoading]);

  // Load history whenever active conversation changes
  useEffect(() => {
    if (!activeConversationId) return;
    (async () => {
      try {
        addDebugInfo(`🔵 Loading history for conversation: ${activeConversationId}`);
        const hist = await getJSON(`/api/chat/history/${activeConversationId}`);
        setMessages(hist?.messages || []);
        addDebugInfo(`🔵 Loaded ${hist?.messages?.length || 0} messages`);
      } catch (e) {
        console.error('Failed to load history', e);
        addDebugInfo(`❌ Failed to load history: ${e.message}`);
        setMessages([]);
      }
    })();
  }, [activeConversationId]);

  async function handleNewConversation() {
    try {
      addDebugInfo('🔵 Creating new conversation...');
      const created = await postJSON('/api/chat/new', {
        user_id: userId,
        title: 'New Conversation'
      });
      const convId = created?.conversation_id;
      if (convId) {
        const next = [{ id: convId, title: created?.title || 'New Conversation' }, ...conversations];
        setConversations(next);
        setActiveConversationId(convId);
        setMessages([]);
        setUploadedDocs([]);
        addDebugInfo(`✅ Created conversation: ${convId}`);
      }
    } catch (e) {
      console.error('Failed to create conversation', e);
      addDebugInfo(`❌ Failed to create conversation: ${e.message}`);
    }
  }

  async function handleDeleteConversation(convId) {
    try {
      addDebugInfo(`🔵 Deleting conversation: ${convId}`);
      await fetch(`${BACKEND_URL}/api/chat/${convId}`, { method: 'DELETE' });
      const next = conversations.filter(c => c.id !== convId);
      setConversations(next);
      if (activeConversationId === convId) {
        setActiveConversationId(next[0]?.id || null);
        setMessages([]);
      }
      addDebugInfo(`✅ Deleted conversation: ${convId}`);
    } catch (e) {
      console.error('Failed to delete conversation', e);
      addDebugInfo(`❌ Failed to delete conversation: ${e.message}`);
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || !activeConversationId || sending || streaming) return;

    addDebugInfo(`🔵 Sending message: "${text.substring(0, 50)}..."`);
    setSending(true);
    setStreaming(true);

    // Append user message
    const userMsg = {
      id: `temp-${Date.now()}`,
      conversation_id: activeConversationId,
      role: 'user',
      content: text,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMsg]);

    // Placeholder assistant message to stream into
    const assistantTempId = `assistant-${Date.now()}`;
    setMessages(prev => [
      ...prev,
      {
        id: assistantTempId,
        conversation_id: activeConversationId,
        role: 'assistant',
        content: '',
        created_at: new Date().toISOString()
      }
    ]);

    setInput('');

    try {
      const body = {
        user_id: userId,
        conversation_id: activeConversationId,
        message: text,
        stream: true,
        include_sources: true
      };

      let currentText = '';
      let assistantIndexRef = null;

      // Find the placeholder index lazily
      const ensureAssistantIndex = () => {
        if (assistantIndexRef !== null) return assistantIndexRef;
        assistantIndexRef = messages.length + 1; // user appended + this assistant
        return assistantIndexRef;
      };

      for await (const evt of postStream('/api/chat/send', body)) {
        if (evt?.type === 'delta') {
          currentText += (currentText ? '' : '') + (evt.text || '');
          const idx = ensureAssistantIndex();
          setMessages(prev => {
            const copy = [...prev];
            const aIdx = Math.min(idx, copy.length - 1);
            if (copy[aIdx] && copy[aIdx].role === 'assistant') {
              copy[aIdx] = { ...copy[aIdx], content: currentText };
            }
            return copy;
          });
        } else if (evt?.type === 'final') {
          const idx = ensureAssistantIndex();
          setMessages(prev => {
            const copy = [...prev];
            const aIdx = Math.min(idx, copy.length - 1);
            if (copy[aIdx] && copy[aIdx].role === 'assistant') {
              copy[aIdx] = { ...copy[aIdx], content: evt.answer || currentText || '' };
            }
            return copy;
          });
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

  async function handleUpload(file, docType = 'expert_analysis') {
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
      form.append('document_type', docType);
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

      // Track uploaded doc locally
      setUploadedDocs(prev => [
        {
          id: data.document_record_id || data.document_id,
          filename: file.name,
          document_type: docType,
          linked_to_conversation: data.linked_to_conversation
        },
        ...prev
      ]);

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
    addDebugInfo('🔵 Dropzone clicked');
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
                <li className="text-muted">No documents uploaded in this session.</li>
              ) : (
                uploadedDocs.map(d => (
                  <li key={d.id} className="mb-1">
                    📄 {d.filename} <span className="text-muted">({d.document_type})</span>
                  </li>
                ))
              )}
            </ul>
          </div>
        </Col>

        {/* Main */}
        <Col md="9" lg="9" className="tax-main">
          <div className="d-flex justify-content-between align-items-center tax-header">
            <div>
              <h5 className="mb-1">AI Tax Assistant</h5>
              <small className="text-muted">Powered by multi-agent intelligence system</small>
            </div>
            <div className="tax-header-actions">
              <Button color="link" className="p-2 text-muted" aria-label="Search" disabled>
                🔍
              </Button>
              <Button color="link" className="p-2 text-muted" aria-label="Help" disabled>
                ❓
              </Button>
              <Button color="link" className="p-2 text-muted" aria-label="Settings" disabled>
                ⚙️
              </Button>
              <div
                className="d-inline-block rounded-circle bg-light border text-center align-middle ml-2"
                style={{ width: 32, height: 32, lineHeight: '32px' }}
                aria-label="Profile">
                👤
              </div>
            </div>
          </div>

          {/* Debug Panel */}
          {process.env.NODE_ENV === 'development' && (
            <Card className="mb-3 bg-light">
              <CardBody>
                <h6>🐛 Debug Panel</h6>
                <div style={{ fontSize: '12px', fontFamily: 'monospace' }}>
                  <div>
                    User ID: <strong>{userId || 'undefined'}</strong>
                  </div>
                  <div>
                    Active Conversation: <strong>{activeConversationId || 'undefined'}</strong>
                  </div>
                  <div>
                    Backend URL: <strong>{BACKEND_URL || 'undefined'}</strong>
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
                  documents.
                </p>
              </CardBody>
            </Card>
          )}

          {/* Dropzone */}
          <Card className="mb-3 tax-dropzone" data-testid="dropzone">
            <CardBody className="text-center">
              <div
                onClick={onDropZoneClick}
                onDrop={onDrop}
                onDragOver={onDragOver}
                style={{
                  cursor: 'pointer',
                  padding: '20px',
                  border: uploading ? '2px dashed #007bff' : '2px dashed #dee2e6',
                  borderRadius: '8px',
                  backgroundColor: uploading ? '#f8f9fa' : 'transparent'
                }}>
                <div className="display-6 mb-2">{uploading ? '⏳' : '☁️'}</div>
                <div>
                  {uploading ? (
                    <span className="text-primary">Uploading...</span>
                  ) : (
                    <>
                      Drop documents here or{' '}
                      <strong style={{ color: '#007bff', textDecoration: 'underline' }} onClick={onDropZoneClick}>
                        click to upload
                      </strong>
                    </>
                  )}
                </div>
                <small className="text-muted d-block mt-2">
                  PDF, DOC, DOCX, TXT • Tax codes, contracts, regulations, case law
                </small>
              </div>

              {/* Backup upload button */}
              <Button color="outline-primary" size="sm" className="mt-3" onClick={onDropZoneClick} disabled={uploading}>
                📎 {uploading ? 'Uploading...' : 'Choose File'}
              </Button>

              {/* Hidden file input */}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                onChange={onFileChange}
                style={{ display: 'none' }}
              />
            </CardBody>
          </Card>

          {/* Messages */}
          <div className="mb-3" style={{ minHeight: 240, maxHeight: 420, overflowY: 'auto', padding: '0 6px' }}>
            {messages.map(m => (
              <div
                key={m.id}
                className={`mb-2 p-2 rounded ${m.role === 'user' ? 'bg-primary text-white' : 'bg-light'}`}
                style={{ maxWidth: '85%', marginLeft: m.role === 'user' ? 'auto' : '0' }}>
                <div className="small text-muted mb-1">{m.role === 'user' ? 'You' : 'Assistant'}</div>
                <div style={{ whiteSpace: 'pre-wrap' }}>{m.content}</div>
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
