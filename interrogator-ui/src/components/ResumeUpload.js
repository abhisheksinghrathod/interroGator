// src/components/ResumeUpload.js

import React, { useState, useEffect } from 'react';
import api from '../api/client';

export default function ResumeUpload({ onSelect }) {
  const [resumes, setResumes] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  // Fetch resumes
  const loadResumes = async () => {
    try {
      const res = await api.get('resumes/');
      const list = Array.isArray(res.data) ? res.data : res.data.results ?? [];
      setResumes(list);
    } catch (err) {
      console.error('Failed to load resumes:', err);
    }
  };

  useEffect(() => {
    loadResumes();
  }, []);

  const getFilename = url => {
    try {
      const parts = url.split('/');
      return decodeURIComponent(parts[parts.length - 1]);
    } catch {
      return url;
    }
  };

  const handleFileChange = e => {
    setFile(e.target.files[0]);
    setError('');
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      // don't set Content-Type manually—let axios handle the boundary
      await api.post('resumes/', form);
      setFile(null);
      await loadResumes();
    } catch (err) {
      // dump full response so you can see what's coming back
      console.error('Upload failed response:', err.response);
      let msg = 'Upload failed. Please try again.';
      if (err.response) {
        // if DRF sent field errors
        if (err.response.data.file) {
          msg = err.response.data.file.join(', ');
        }
        // or a general detail
        else if (err.response.data.detail) {
          msg = err.response.data.detail;
        }
        // else show raw JSON
        else {
          msg = JSON.stringify(err.response.data);
        }
      } else {
        msg = err.message;
      }
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  const handleStart = () => {
    if (selectedId) onSelect(selectedId);
  };

  return (
    <div style={{ padding: '2rem' }}>
      <h2>Upload a Resume</h2>
      <input
        type="file"
        accept=".pdf,.doc,.docx"
        onChange={handleFileChange}
        disabled={uploading}
      />
      <button
        onClick={handleUpload}
        disabled={!file || uploading}
        style={{ marginLeft: '0.5rem' }}
      >
        {uploading ? 'Uploading…' : 'Upload'}
      </button>
      {error && (
        <p style={{ color: 'red', whiteSpace: 'pre-wrap' }}>{error}</p>
      )}

      <hr style={{ margin: '1.5rem 0' }} />

      <h2>Select a Resume</h2>
      {resumes.length === 0 && <p>No resumes uploaded yet.</p>}
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {resumes.map(r => (
          <li key={r.id} style={{ marginBottom: '0.5rem' }}>
            <label>
              <input
                type="radio"
                name="resume"
                value={r.id}
                checked={selectedId === r.id}
                onChange={() => setSelectedId(r.id)}
                style={{ marginRight: '0.5rem' }}
              />
              {getFilename(r.file)}
            </label>
          </li>
        ))}
      </ul>

      <button
        disabled={!selectedId}
        onClick={handleStart}
        style={{ marginTop: '1rem' }}
      >
        Start Interview
      </button>
    </div>
  );
}
