// src/App.js

import React, { useState } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  useNavigate
} from 'react-router-dom';
import ResumeUpload from './components/ResumeUpload';
import InterviewPage from './components/InterviewPage';
import api from './api/client';

function Home() {
  const navigate = useNavigate();
  const [error, setError] = useState('');

  const handleSelect = async (resumeId) => {
    setError('');
    try {
      // POST the correct field name: resume_id
      const res = await api.post('sessions/', { resume_id: resumeId });
      const sessionId = res.data.id;
      navigate(`/interview/${sessionId}`);
    } catch (err) {
      console.error('Failed to start session:', err.response?.data || err);
      let msg = 'Could not start interview. Please try again.';
      if (err.response?.data) {
        const data = err.response.data;
        msg = Object.entries(data)
          .map(([field, msgs]) => `${field}: ${msgs.join(', ')}`)
          .join(' | ');
      }
      setError(msg);
    }
  };

  return (
    <div style={{ padding: '2rem' }}>
      <ResumeUpload onSelect={handleSelect} />
      {error && (
        <div style={{ marginTop: '1rem', color: 'red' }}>
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/interview/:sessionId" element={<InterviewPage />} />
      </Routes>
    </Router>
  );
}
