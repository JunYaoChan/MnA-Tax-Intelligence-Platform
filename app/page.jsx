'use client';

import React from 'react';
import { Container, Card, CardBody, Button, Row, Col } from 'reactstrap';
import useAuthUser from '../lib/useAuthUser';
import TaxAssistantInterface from '../components/TaxAssistantInterface';
import AnchorLink from '../components/AnchorLink';

const LandingPage = () => (
  <Container className="py-5">
    <Row className="justify-content-center">
      <Col lg={8}>
        <div className="text-center mb-5">
          <h1 className="display-4 mb-3">M&A Tax Intelligence Platform</h1>
          <p className="lead text-muted mb-4">
            Advanced AI-powered tax research and analysis for complex M&A transactions
          </p>
        </div>

        <Row className="mb-4">
          <Col md={4} className="mb-3">
            <Card className="h-100 border-0 shadow-sm">
              <CardBody className="text-center">
                <div className="mb-3" style={{ fontSize: '2rem' }}>
                  🔍
                </div>
                <h5>Intelligent Research</h5>
                <p className="text-muted small">AI-powered search across regulations, case law, and precedents</p>
              </CardBody>
            </Card>
          </Col>
          <Col md={4} className="mb-3">
            <Card className="h-100 border-0 shadow-sm">
              <CardBody className="text-center">
                <div className="mb-3" style={{ fontSize: '2rem' }}>
                  📊
                </div>
                <h5>Expert Analysis</h5>
                <p className="text-muted small">Professional-grade synthesis and recommendations</p>
              </CardBody>
            </Card>
          </Col>
          <Col md={4} className="mb-3">
            <Card className="h-100 border-0 shadow-sm">
              <CardBody className="text-center">
                <div className="mb-3" style={{ fontSize: '2rem' }}>
                  ⚡
                </div>
                <h5>Fast Results</h5>
                <p className="text-muted small">Get comprehensive answers in under 20 seconds</p>
              </CardBody>
            </Card>
          </Col>
        </Row>

        <Card className="border-0 shadow-sm">
          <CardBody className="text-center py-5">
            <h3 className="mb-3">Ready to Get Started?</h3>
            <p className="text-muted mb-4">
              Sign in to access the full M&A Tax Intelligence Platform and start researching complex tax matters with AI
              assistance.
            </p>
            <AnchorLink href="/auth/login" className="btn btn-primary btn-lg" testId="landing-login-button">
              Sign In to Continue
            </AnchorLink>
          </CardBody>
        </Card>

        <div className="text-center mt-4">
          <small className="text-muted">Secure authentication powered by Auth0</small>
        </div>
      </Col>
    </Row>
  </Container>
);

const LoadingScreen = () => (
  <Container className="py-5">
    <Row className="justify-content-center">
      <Col xs="auto">
        <div className="text-center">
          <div className="spinner-border text-primary mb-3" role="status">
            <span className="sr-only">Loading...</span>
          </div>
          <p className="text-muted">Loading...</p>
        </div>
      </Col>
    </Row>
  </Container>
);

export default function Index() {
  const { user, isLoading } = useAuthUser();

  // Show loading screen while checking authentication
  if (isLoading) {
    return <LoadingScreen />;
  }

  // Show landing page if user is not logged in
  if (!user) {
    return <LandingPage />;
  }

  // Show the tax assistant interface if user is logged in
  return <TaxAssistantInterface />;
}
