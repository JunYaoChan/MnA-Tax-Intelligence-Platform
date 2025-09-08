'use client';

import React from 'react';
import Hero from '../components/Hero';
import Content from '../components/Content';
import TaxAssistantInterface from '../components/TaxAssistantInterface';
import Loading from '../components/Loading';
import { useUser } from '@auth0/nextjs-auth0';

export default function Index() {
  const { user, isLoading } = useUser();

  if (isLoading) {
    return <Loading />;
  }

  return user ? (
    <TaxAssistantInterface />
  ) : (
    <>
      <Hero />
      <hr />
      <Content />
    </>
  );
}
