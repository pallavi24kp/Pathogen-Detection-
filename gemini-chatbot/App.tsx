import React from 'react';
import { Chatbot } from './components/Chatbot';
import { BotIcon } from './components/Icons';

const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-100 dark:from-gray-900 dark:to-blue-900 text-gray-800 dark:text-gray-200 font-sans">
      <main className="container mx-auto px-4 py-8 flex flex-col items-center justify-center min-h-screen">
        <header className="text-center mb-6">
          <div className="inline-block bg-white dark:bg-gray-800 p-3 rounded-full shadow-md mb-3">
            <BotIcon className="w-8 h-8 text-blue-500" />
          </div>
          <h1 className="text-3xl md:text-4xl font-bold text-gray-900 dark:text-white">
            Gemini Chatbot
          </h1>
        </header>
        <Chatbot />
         <footer className="text-center mt-8">
          <p className="text-sm text-gray-500 dark:text-gray-500">
            Powered by Google Gemini API.
          </p>
        </footer>
      </main>
    </div>
  );
};

export default App;