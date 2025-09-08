'use client';

import React from 'react';
import { Row, Col, Card, CardBody, ListGroup, ListGroupItem, Button, Input } from 'reactstrap';

const recentChats = ['IRC Section 368 Analysis', 'Cross-border Merger Struct...', 'Tax-free Reorganization Rules'];

const TaxAssistantInterface = () => {
  return (
    <div className="tax-ui container-fluid" data-testid="tax-interface">
      <Row>
        {/* Sidebar */}
        <Col md="3" lg="3" className="tax-sidebar">
          <div className="sidebar-section">
            <div className="d-flex justify-content-between align-items-center mb-2">
              <h6 className="mb-0">Recent Chats</h6>
              <Button size="sm" color="light" className="px-2 py-1">
                +
              </Button>
            </div>
            <ListGroup flush className="tax-recent-chats" data-testid="recent-chats">
              {recentChats.map((title, idx) => (
                <ListGroupItem key={idx} className={idx === 0 ? 'active' : ''}>
                  {title}
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
        </Col>

        {/* Main */}
        <Col md="9" lg="9" className="tax-main">
          <div className="d-flex justify-content-between align-items-center tax-header">
            <div>
              <h5 className="mb-1">AI Tax Assistant</h5>
              <small className="text-muted">Powered by multi-agent intelligence system</small>
            </div>
            <div className="tax-header-actions">
              <Button color="link" className="p-2 text-muted" aria-label="Search">
                🔍
              </Button>
              <Button color="link" className="p-2 text-muted" aria-label="Help">
                ❓
              </Button>
              <Button color="link" className="p-2 text-muted" aria-label="Settings">
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

          <Card className="mb-5 tax-dropzone" data-testid="dropzone">
            <CardBody className="text-center">
              <div className="display-6 mb-2">☁️</div>
              <div>
                Drop documents here or{' '}
                <a href="#" onClick={e => e.preventDefault()}>
                  click to upload
                </a>
              </div>
              <small className="text-muted">PDF, DOC, DOCX, TXT • Tax codes, contracts, regulations, case law</small>
            </CardBody>
          </Card>

          <div className="tax-input d-flex align-items-center">
            <Input
              type="text"
              placeholder="Ask about M&A tax matters, upload documents for analysis, or start a new topic..."
              className="mr-2"
              data-testid="chat-input"
            />
            <Button color="primary" data-testid="send-button">
              Send
            </Button>
          </div>
        </Col>
      </Row>
    </div>
  );
};

export default TaxAssistantInterface;
