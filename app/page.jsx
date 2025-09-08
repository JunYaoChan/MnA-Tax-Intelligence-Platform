'use client';

import React from 'react';
import TaxAssistantInterface from '../components/TaxAssistantInterface';

export default function Index() {
  // Always render the chatbot UI. The component itself handles anonymous users by
  // falling back to a demo user id, and integrates with the backend.
  return <TaxAssistantInterface />;
}
