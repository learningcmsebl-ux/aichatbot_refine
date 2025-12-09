import React from 'react';

export const Header: React.FC = () => {
  return (
    <div
      className="bg-gradient-to-r from-[#003366] via-[#004080] to-[#0052A5] text-white px-7 py-3 flex items-center justify-between"
      style={{
        background: 'linear-gradient(135deg, #003366 0%, #004080 50%, #0052A5 100%)',
      }}
    >
      <div className="flex items-center gap-4">
        <img
          src="/dia-avatar.png"
          alt="EBL DIA 2.0"
          className="w-18 h-18 rounded-xl object-cover border-3 border-white/50 shadow-md"
          style={{
            width: '72px',
            height: '72px',
            borderRadius: '12px',
            objectFit: 'cover',
            objectPosition: 'center 20%',
            border: '3px solid rgba(255, 255, 255, 0.5)',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
          }}
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = 'none';
          }}
        />
        <div className="flex flex-col justify-center">
          <h1 className="text-3xl font-bold m-0 mb-0.5" style={{ fontSize: '28px', fontWeight: 700 }}>
            EBL DIA 2.0
          </h1>
          <span className="text-sm text-blue-100" style={{ fontSize: '14px', color: '#e3eaf7', fontWeight: 400 }}>
            Digital Intelligent Assistant
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 text-sm ml-auto" style={{ fontSize: '14px' }}>
        <span
          className="w-2.5 h-2.5 bg-green-400 rounded-full status-dot"
          style={{
            width: '10px',
            height: '10px',
            borderRadius: '50%',
            background: '#4ade80',
          }}
        ></span>
        <span>Connected</span>
      </div>
    </div>
  );
};
