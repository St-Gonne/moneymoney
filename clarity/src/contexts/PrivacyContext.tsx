import React, { createContext, useContext } from 'react';

const PrivacyContext = createContext<boolean>(false);

export const usePrivacy = () => useContext(PrivacyContext);

export const PrivacyProvider: React.FC<{ children: React.ReactNode; isPrivacyShieldActive: boolean }> = ({ children, isPrivacyShieldActive }) => {
  return (
    <PrivacyContext.Provider value={isPrivacyShieldActive}>
      {children}
    </PrivacyContext.Provider>
  );
};
