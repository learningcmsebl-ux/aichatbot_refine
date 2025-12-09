import React from 'react';
import { ChatInterface } from './components/ChatInterface';
import './index.css';

function App() {
  return (
    <div className="App" style={{ width: '100%', height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
      <ChatInterface />
    </div>
  );
}

export default App;
