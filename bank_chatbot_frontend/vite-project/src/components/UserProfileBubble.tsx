import React from 'react';

interface UserProfileBubbleProps {
  userName?: string;
}

export const UserProfileBubble: React.FC<UserProfileBubbleProps> = () => {
  return (
    <div
      className="fixed bottom-6 right-6 flex flex-col items-center gap-3 bg-white rounded-2xl px-6 py-5 shadow-2xl hover:shadow-2xl transition-all cursor-pointer group"
      style={{
        position: 'fixed',
        bottom: 'calc(5vh + 20px)', // Align with chat container bottom: 5vh margin (centered 90vh container) + 20px (InputArea container padding)
        right: 'max(24px, calc((100vw - 900px) / 2 + 900px + 24px))', // Responsive: minimum 24px or aligned to right of chat container
        backgroundColor: '#ffffff',
        borderRadius: '20px',
        padding: '24px 28px',
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '12px',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        cursor: 'pointer',
        zIndex: 1000,
        border: '1px solid rgba(0, 0, 0, 0.05)',
        minWidth: '140px',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 12px 32px rgba(0, 0, 0, 0.2), 0 4px 12px rgba(0, 0, 0, 0.15)';
        e.currentTarget.style.transform = 'translateY(-4px) scale(1.02)';
        e.currentTarget.style.borderColor = 'rgba(13, 147, 117, 0.2)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.1)';
        e.currentTarget.style.transform = 'translateY(0) scale(1)';
        e.currentTarget.style.borderColor = 'rgba(0, 0, 0, 0.05)';
      }}
    >
      {/* Avatar - Rectangular */}
      <div
        className="bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center flex-shrink-0"
        style={{
          width: '100px',
          height: '120px',
          borderRadius: '12px',
          background: 'linear-gradient(135deg, #0d9375 0%, #0a7a5f 100%)',
          boxShadow: '0 4px 16px rgba(13, 147, 117, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2)',
          transition: 'all 0.3s ease',
          padding: '4px',
        }}
      >
        <div
          className="bg-cover bg-center"
          style={{
            width: '100%',
            height: '100%',
            borderRadius: '10px',
            backgroundImage: 'url(/dia-avatar.png)',
            backgroundSize: 'cover',
            backgroundPosition: 'center 20%',
            backgroundRepeat: 'no-repeat',
            border: '3px solid rgba(255, 255, 255, 0.4)',
          }}
        />
      </div>
      
      {/* Name and Title */}
      <div className="flex flex-col items-center gap-1">
        <span
          className="text-base font-bold text-gray-900 text-center"
          style={{
            fontSize: '16px',
            fontWeight: 700,
            color: '#111827',
            whiteSpace: 'nowrap',
            letterSpacing: '-0.2px',
            lineHeight: '1.2',
          }}
        >
          EBL DIA 2.0
        </span>
        <span
          className="text-xs font-medium text-gray-600 text-center"
          style={{
            fontSize: '11px',
            fontWeight: 500,
            color: '#4b5563',
            whiteSpace: 'nowrap',
            letterSpacing: '0.1px',
            lineHeight: '1.3',
          }}
        >
          Digital Intelligent Assistant
        </span>
      </div>
    </div>
  );
};

