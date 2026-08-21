import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PhoneCall, MonitorUp, X, ShieldAlert } from 'lucide-react';

interface HelpModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const HelpModal: React.FC<HelpModalProps> = ({ isOpen, onClose }) => {
  const [activeStep, setActiveStep] = useState<'initial' | 'screenshare'>('initial');

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <motion.div 
          initial={{ opacity: 0 }} 
          animate={{ opacity: 1 }} 
          exit={{ opacity: 0 }} 
          className="absolute inset-0 bg-black/80 backdrop-blur-md"
          onClick={onClose}
        />
        
        <motion.div 
          initial={{ scale: 0.95, opacity: 0, y: 20 }}
          animate={{ scale: 1, opacity: 1, y: 0 }}
          exit={{ scale: 0.95, opacity: 0, y: 20 }}
          className="relative bg-theme-surface w-full h-full sm:h-auto sm:max-w-4xl sm:rounded-3xl shadow-2xl flex flex-col overflow-hidden border border-theme"
        >
          {/* Header */}
          <div className="bg-red-500/10 border-b border-red-500/20 p-5 flex items-center justify-between">
            <div className="flex items-center gap-3 text-red-500">
              <ShieldAlert className="w-12 h-12" />
              <h2 className="text-4xl font-black tracking-tight">Need Help?</h2>
            </div>
            <button 
              onClick={onClose}
              className="p-2 rounded-full hover:bg-theme-hover text-theme-muted hover:text-theme-primary transition-colors"
            >
              <X className="w-10 h-10" />
            </button>
          </div>

          <div className="p-6 sm:p-8 space-y-6">
            {activeStep === 'initial' ? (
              <>
                <p className="text-2xl sm:text-3xl text-theme-primary font-bold leading-relaxed">
                  Don't worry! Your family administrator is just a click away. How would you like to get help?
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 sm:gap-12 mt-8">
                  <a 
                    href="tel:+919999999999" // Replace with actual number if provided
                    className="p-8 sm:p-12 rounded-3xl border-2 border-theme bg-theme-subtle hover:border-emerald-500 hover:bg-emerald-500/5 group transition-all text-center space-y-3 cursor-pointer block"
                  >
                    <div className="w-24 h-24 mx-auto bg-emerald-500/10 text-emerald-500 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                      <PhoneCall className="w-12 h-12" />
                    </div>
                    <div>
                      <h3 className="font-black text-3xl text-theme-primary">Call Family Admin</h3>
                      <p className="text-xl text-theme-secondary mt-2 font-bold">Voice call immediately</p>
                    </div>
                  </a>

                  <button 
                    onClick={() => setActiveStep('screenshare')}
                    className="p-8 sm:p-12 rounded-3xl border-2 border-theme bg-theme-subtle hover:border-blue-500 hover:bg-blue-500/5 group transition-all text-center space-y-3 cursor-pointer"
                  >
                    <div className="w-24 h-24 mx-auto bg-blue-500/10 text-blue-500 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                      <MonitorUp className="w-12 h-12" />
                    </div>
                    <div>
                      <h3 className="font-black text-3xl text-theme-primary">Share Screen</h3>
                      <p className="text-xl text-theme-secondary mt-2 font-bold">Share screen with Family Admin</p>
                    </div>
                  </button>
                </div>
              </>
            ) : (
              <motion.div 
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-6"
              >
                <div className="space-y-2">
                  <h3 className="text-3xl font-black text-theme-primary flex items-center gap-2">
                    <MonitorUp className="w-10 h-10 text-blue-500" />
                    Share Screen via Chrome Remote
                  </h3>
                  <p className="text-2xl text-theme-secondary font-bold">
                    To let the administrator assist and view your screen:
                  </p>
                </div>

                <div className="bg-theme-subtle border-4 border-blue-500/20 rounded-3xl p-8 space-y-8">
                  <div className="flex gap-4">
                    <div className="w-12 h-12 rounded-full bg-blue-500 text-white flex items-center justify-center font-bold shrink-0">1</div>
                    <p className="text-2xl text-theme-primary font-bold pt-1.5 leading-snug">
                      Click the button below to open Google Chrome Remote Desktop.
                    </p>
                  </div>
                  <div className="flex gap-4">
                    <div className="w-12 h-12 rounded-full bg-blue-500 text-white flex items-center justify-center font-bold shrink-0">2</div>
                    <p className="text-2xl text-theme-primary font-bold pt-1.5 leading-snug">
                      Click <strong className="text-blue-500">"Generate Code"</strong> on that page.
                    </p>
                  </div>
                  <div className="flex gap-4">
                    <div className="w-12 h-12 rounded-full bg-blue-500 text-white flex items-center justify-center font-bold shrink-0">3</div>
                    <p className="text-2xl text-theme-primary font-bold pt-1.5 leading-snug">
                      Call Family Admin and read the 12-digit code to him. He will instantly connect to your screen!
                    </p>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button 
                    onClick={() => setActiveStep('initial')}
                    className="btn btn-lg btn-outline font-black text-2xl py-6 flex-1 border-4"
                  >
                    Go Back
                  </button>
                  <a 
                    href="https://remotedesktop.google.com/support"
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-lg bg-blue-600 hover:bg-blue-500 text-white font-black text-2xl py-6 flex-[2] text-center justify-center border-none shadow-2xl shadow-blue-500/40"
                  >
                    Open Remote Desktop
                  </a>
                </div>
              </motion.div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
