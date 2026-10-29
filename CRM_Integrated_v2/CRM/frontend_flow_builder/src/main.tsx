import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

const mountNode = document.getElementById('root') || document.getElementById('builderApp') || document.body;

if (mountNode) {
  ReactDOM.createRoot(mountNode).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
