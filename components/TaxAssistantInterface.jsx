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
  const fileInputRef = useRef(null);
  const chatEndRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streaming]);

  // Load or create conversation on user ready
  useEffect(() => {
    if (!userId || isLoading) return;
    (async () => {
      try {
        // Fetch list
        const res = await getJSON(`/api/chat/list?user_id=${encodeURIComponent(userId)}`);
        const convs = res?.conversations || [];
        setConversations(convs);
        if (convs.length > 0) {
          setActiveConversationId(convs[0].id);
        } else {
          // Create if none
          const created = await postJSON('/api/chat/new', {
            user_id: userId,
            title: 'New Conversation'
          });
          const convId = created?.conversation_id;
          if (convId) {
            setConversations([{ id: convId, title: created?.title || 'New Conversation' }]);
            setActiveConversationId(convId);
          }
        }
      } catch (e) {
        console.error('Failed to load conversations', e);
      }
    })();
  }, [userId, isLoading]);

  // Load history whenever active conversation changes
  useEffect(() => {
    if (!activeConversationId) return;
    (async () => {
      try {
        const hist = await getJSON(`/api/chat/history/${activeConversationId}`);
        setMessages(hist?.messages || []);
      } catch (e) {
        console.error('Failed to load history', e);
        setMessages([]);
      }
    })();
  }, [activeConversationId]);

  async function handleNewConversation() {
    try {
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
      }
    } catch (e) {
      console.error('Failed to create conversation', e);
    }
  }

  async function handleDeleteConversation(convId) {
    try {
      await fetch(`${BACKEND_URL}/api/chat/${convId}`, { method: 'DELETE' });
      const next = conversations.filter(c => c.id !== convId);
      setConversations(next);
      if (activeConversationId === convId) {
        setActiveConversationId(next[0]?.id || null);
        setMessages([]);
      }
    } catch (e) {
      console.error('Failed to delete conversation', e);
    }
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || !activeConversationId || sending || streaming) return;
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
          currentText += (currentText ? ' ' : '') + (evt.text || '');
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
        }
      }
    } catch (e) {
      console.error('Send failed', e);
    } finally {
      setSending(false);
      setStreaming(false);
    }
  }

  async function handleUpload(file, docType = 'expert_analysis') {
    if (!file || !activeConversationId) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('document_type', docType);
      form.append('metadata', JSON.stringify({ uploaded_via: 'ui', size: file.size }));
      form.append('conversation_id', activeConversationId);
      form.append('user_id', userId);

      const res = await fetch(`${BACKEND_URL}/upload/document`, {
        method: 'POST',
        body: form
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || 'Upload failed');

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

      // Provide assistant acknowledgement in chat
      const ack = {
        id: `sys-${Date.now()}`,
        conversation_id: activeConversationId,
        role: 'assistant',
        content: `Received document "${file.name}". Processing complete. You can now ask questions about it.`,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, ack]);
    } catch (e) {
      console.error('Upload failed', e);
      const err = {
        id: `err-${Date.now()}`,
        conversation_id: activeConversationId,
        role: 'assistant',
        content: `Upload failed: ${e.message || e.toString()}`,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, err]);
    } finally {
      setUploading(false);
    }
  }

  function onDropZoneClick(e) {
    e.preventDefault();
    fileInputRef.current?.click();
  }

  function onFileChange(e) {
    const f = e.target.files?.[0];
    if (f) handleUpload(f);
    // reset input
    e.target.value = '';
  }

  function onDrop(e) {
    e.preventDefault();
    const f = e.dataTransfer?.files?.[0];
    if (f) handleUpload(f);
  }

  function onDragOver(e) {
    e.preventDefault();
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
                      className={
                        c.id === activeConversationId
                          ? 'active d-flex justify-content-between align-items-center'
                          : 'd-flex justify-content-between align-items-center'
                      }
                      onClick={() => setActiveConversationId(c.id)}
                      style={{ cursor: 'pointer' }}>
                      <span>{c.title || 'Conversation'}</span>
                      <Button
                        size="sm"
                        color="link"
                        className="text-danger p-0"
                        title="Delete"
                        onClick={e => {
                          e.stopPropagation();
                          handleDeleteConversation(c.id);
                        }}>
                        ×
                      </Button>
                    </ListGroupItem>
                  ))}
            </ListGroup>
          </div>

          <div className="sidebar-section mt-4">
            <h6 className="mb-2">System Status</h6>
            <ul className="list-unstyled mb-0" data-testid="system-status">
              <li className="d-flex align-items-center mb-2">
                <span className="status-dot bg-success" /> Multi-Agent System Online
              </li>
              <li className="d-flex align-items-center mb-2">
                <span className="status-dot bg-success" /> Knowledge Base Connected
              </li>
              <li className="d-flex align-items-center">
                <span className="status-dot bg-success" /> Document Processing Ready
              </li>
            </ul>
          </div>

          <div className="sidebar-section mt-4">
            <h6 className="mb-2">Uploaded Documents</h6>
            <ul className="list-unstyled mb-0 small">
              {uploadedDocs.length === 0 ? (
                <li className="text-muted">No documents uploaded in this session.</li>
              ) : (
                uploadedDocs.map(d => (
                  <li key={d.id} className="mb-1">
                    {d.filename} <span className="text-muted">({d.document_type})</span>
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
          <Card
            className="mb-3 tax-dropzone"
            data-testid="dropzone"
            onClick={onDropZoneClick}
            onDrop={onDrop}
            onDragOver={onDragOver}
            style={{ cursor: 'pointer' }}>
            <CardBody className="text-center">
              <div className="display-6 mb-2">☁️</div>
              <div>
                Drop documents here or{' '}
                <a
                  href="#"
                  onClick={e => {
                    e.preventDefault();
                    onDropZoneClick(e);
                  }}>
                  click to upload
                </a>
              </div>
              <small className="text-muted">PDF, DOC, DOCX, TXT • Tax codes, contracts, regulations, case law</small>
              {uploading && <div className="mt-2 small text-primary">Uploading...</div>}
              <input ref={fileInputRef} type="file" hidden onChange={onFileChange} />
            </CardBody>
          </Card>

          {/* Messages */}
          <div className="mb-3" style={{ minHeight: 240, maxHeight: 420, overflowY: 'auto', padding: '0 6px' }}>
            {messages.map(m => (
              <div
                key={m.id}
                className={`mb-2 p-2 rounded ${m.role === 'user' ? 'bg-primary text-white' : 'bg-light'}`}
                style={{ maxWidth: '85%' }}>
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
