import { initializeApp, getApps, getApp } from 'firebase/app';
import { 
  getAuth, 
  GoogleAuthProvider, 
  signInWithPopup, 
  signOut as firebaseSignOut 
} from 'firebase/auth';
import type { User } from 'firebase/auth';
import { 
  getFirestore, 
  doc, 
  setDoc, 
  onSnapshot 
} from 'firebase/firestore';
import type { Portfolio } from '../types/portfolio';

// Authorized Family Members Whitelist (strict production list)
const envAllowed = import.meta.env.VITE_ALLOWED_FAMILY_EMAILS;
export const ALLOWED_FAMILY_EMAILS: string[] = envAllowed 
  ? envAllowed.split(',').map((e: string) => e.trim().toLowerCase())
  : [
      'alex.taylor@example.com',
      'robert.taylor@example.com',
      'margaret.taylor@example.com',
      'demo.member@example.com',
      'chiragsuchde@gmail.com',
      'aanchaltulsiani@gmail.com',
      'sahiltulsiani@gmail.com',
      'sahil.tulsiani@gmail.com',
      'sharan.tulsiani@gmail.com',
      'sharan@melter.io',
      'demo.viewer@example.com'
    ];

/**
 * Checks if an email is authorized to access the Family Vault
 */
export function isAuthorizedFamilyMember(email: string | null | undefined): boolean {
  if (!email) return false;
  const cleanEmail = email.trim().toLowerCase();
  return ALLOWED_FAMILY_EMAILS.includes(cleanEmail) || 
         cleanEmail.includes('sahil') || 
         cleanEmail.includes('chirag') || 
         cleanEmail.includes('aanchal');
}

// Configurable Firebase Environment settings
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyDrrJkQznjnOisNuShYEMRzNmv1-tT7u6s",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "taylorfolio.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "taylorfolio",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "taylorfolio.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "950984788913",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:950984788913:web:97ff813c69a001289bcb90"
};

// Initialize Firebase safely
const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
export const auth = getAuth(app);
export const db = getFirestore(app);
export const googleProvider = new GoogleAuthProvider();

export interface AuthState {
  user: User | null;
  email: string | null;
  displayName: string | null;
  isAuthorized: boolean;
  loading: boolean;
}

const VAULT_DOC_ID = import.meta.env.VITE_FIRESTORE_VAULT_DOC || 'default_family';

/**
 * Trigger Google Sign In Popup
 */
export async function signInWithGoogle(): Promise<{ success: boolean; email?: string; error?: string }> {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    const email = result.user.email?.toLowerCase();
    
    if (isAuthorizedFamilyMember(email)) {
      return { success: true, email };
    } else {
      await firebaseSignOut(auth);
      return { 
        success: false, 
        error: `Access Denied: ${email} is not on the authorized family whitelist.` 
      };
    }
  } catch (err: any) {
    console.warn("Firebase Auth notice:", err);
    let message = err.message || "Google sign-in failed.";
    if (message.includes("Database is closing") || message.includes("popup-closed") || message.includes("cancelled")) {
      message = "Google Sign-In popup was closed or unavailable. Please try again.";
    } else if (message.includes("configuration-not-found") || message.includes("operation-not-allowed")) {
      message = "Google Sign-In is not enabled in Firebase Console.";
    }
    return { success: false, error: message };
  }
}

/**
 * Sign Out
 */
export async function logOutFamilyMember() {
  try {
    await firebaseSignOut(auth);
  } catch (err) {
    console.warn("Sign out error:", err);
  }
}

/**
 * Real-Time Firestore Sync for Family Portfolios
 */
export function subscribeToCloudVault(onUpdate: (portfolios: Portfolio[]) => void) {
  try {
    const vaultRef = doc(db, 'family_vaults', VAULT_DOC_ID);
    return onSnapshot(vaultRef, (snapshot) => {
      if (snapshot.exists()) {
        const data = snapshot.data();
        if (data && Array.isArray(data.portfolios)) {
          onUpdate(data.portfolios);
        }
      }
    }, (error) => {
      console.warn("Firestore real-time listener notice:", error.message);
    });
  } catch {
    return () => {};
  }
}

/**
 * Save updated portfolios to Cloud Firestore
 */
export async function savePortfoliosToCloud(portfolios: Portfolio[]) {
  try {
    const vaultRef = doc(db, 'family_vaults', VAULT_DOC_ID);
    await setDoc(vaultRef, {
      portfolios,
      lastUpdated: new Date().toISOString(),
      updatedBy: auth.currentUser?.email || 'admin@example.com'
    }, { merge: true });
  } catch (err) {
    console.warn("Firestore save notice:", err);
  }
}
