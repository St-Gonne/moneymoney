import { useState, useEffect } from 'react';

export type ThemeMode = 'normal' | 'high-contrast-dark' | 'high-contrast-light';
export type FontSizeMode = 'normal' | 'large' | 'xlarge';

export function useThemeManager() {
  const [theme, setTheme] = useState<ThemeMode>(() => {
    return (localStorage.getItem('vault_theme') as ThemeMode) || 'normal';
  });

  const [fontSize, setFontSize] = useState<FontSizeMode>(() => {
    return (localStorage.getItem('vault_font_size') as FontSizeMode) || 'normal';
  });

  // Apply theme to document root
  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'normal') {
      root.removeAttribute('data-theme');
    } else {
      root.setAttribute('data-theme', theme);
    }
    localStorage.setItem('vault_theme', theme);
  }, [theme]);

  // Apply font size to document root
  useEffect(() => {
    const root = document.documentElement;
    if (fontSize === 'normal') {
      root.removeAttribute('data-font-size');
    } else {
      root.setAttribute('data-font-size', fontSize);
    }
    localStorage.setItem('vault_font_size', fontSize);
  }, [fontSize]);

  const toggleTheme = () => {
    setTheme((prev) => {
      if (prev === 'normal') return 'high-contrast-dark';
      if (prev === 'high-contrast-dark') return 'high-contrast-light';
      return 'normal';
    });
  };

  const cycleFontSize = () => {
    setFontSize((prev) => {
      if (prev === 'normal') return 'large';
      if (prev === 'large') return 'xlarge';
      return 'normal';
    });
  };

  return {
    theme,
    setTheme,
    toggleTheme,
    fontSize,
    setFontSize,
    cycleFontSize,
  };
}
