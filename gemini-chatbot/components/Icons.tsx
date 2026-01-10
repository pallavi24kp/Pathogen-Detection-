import React from 'react';

export const KeyIcon: React.FC<React.SVGProps<SVGSVGElement>> = (props) => (
  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" {...props}>
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 7h1a2 2 0 012 2v5a2 2 0 01-2 2h-1m-6 0H6a2 2 0 01-2-2V9a2 2 0 012-2h1m3 0V5a2 2 0 012-2h2a2 2 0 012 2v2m-6 0h6"></path>
  </svg>
);

export const SendIcon: React.FC<React.SVGProps<SVGSVGElement>> = (props) => (
  <svg className="w-6 h-6" viewBox="0 0 24 24" fill="currentColor" {...props}>
    <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
  </svg>
);

export const BotIcon: React.FC<React.SVGProps<SVGSVGElement>> = (props) => (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" {...props}>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M12 5V3m0 18v-2M8 8.5a.5.5 0 01.5-.5h7a.5.5 0 010 1h-7a.5.5 0 01-.5-.5zM12 15.5a.5.5 0 01.5-.5h.01a.5.5 0 010 1H12.5a.5.5 0 01-.5-.5z"></path>
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 2a9 9 0 00-9 9v1.94c0 .64.31 1.23.83 1.6l4.27 3.05a3 3 0 003.8 0l4.27-3.05c.52-.37.83-.96.83-1.6V11a9 9 0 00-9-9z"></path>
    </svg>
);