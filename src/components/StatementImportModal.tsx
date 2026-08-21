import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { 
  FileUp, 
  Lock, 
  CheckCircle, 
  AlertTriangle,
  Sparkles, 
  FileText, 
  ShieldCheck, 
  Globe,
  UploadCloud,
  Server,
  ArrowRight,
  LayoutDashboard,
  Wallet
} from 'lucide-react';
import type { Portfolio, UserProfile } from '../types/portfolio';
import { getRolePermissions } from '../types/portfolio';
import { MoneyMoneyApi, type IngestionApiResponse } from '../services/api';

interface StatementImportModalProps {
  portfolios: Portfolio[];
  onImportSuccess: (portfolioId: string, count: number, newAssets?: any[], updatedPan?: string) => void;
  onNavigateToDashboard?: () => void;
  onNavigateToHoldings?: () => void;
  currentUser?: UserProfile | null;
}

export const StatementImportModal: React.FC<StatementImportModalProps> = ({
  portfolios,
  onImportSuccess,
  onNavigateToDashboard,
  onNavigateToHoldings,
  currentUser
}) => {
  const permissions = getRolePermissions(currentUser?.role, currentUser?.email);
  const [selectedPortfolioId, setSelectedPortfolioId] = useState(portfolios[0]?.id || 'port_primary');
  const [statementType, setStatementType] = useState<'ZERODHA' | 'HDFC' | 'CAMS' | 'SCHWAB' | 'NSDL'>('NSDL');
  const [password, setPassword] = useState('');
  const [fileName, setFileName] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [resultMessage, setResultMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [gateDetails, setGateDetails] = useState<string | null>(null);
  const [importedAssetsSummary, setImportedAssetsSummary] = useState<{ count: number; totalINR: number } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const targetPortfolio = portfolios.find(p => p.id === selectedPortfolioId) || portfolios[0];

  const handleSimulateUpload = (type: 'zerodha' | 'hdfc' | 'cams' | 'schwab' | 'nsdl') => {
    setErrorMessage(null);
    setResultMessage(null);
    setImportedAssetsSummary(null);
    
    let simulatedFileName = '';
    let simulatedPassword = '';
    let simulatedType: 'ZERODHA' | 'HDFC' | 'CAMS' | 'SCHWAB' | 'NSDL' = 'NSDL';
    let mime = 'application/pdf';

    if (type === 'zerodha') {
      simulatedType = 'ZERODHA';
      simulatedFileName = 'Zerodha_ContractNote_EQ_20260814.pdf';
      simulatedPassword = targetPortfolio?.pan || 'KLMNO9012P';
    } else if (type === 'hdfc') {
      simulatedType = 'HDFC';
      simulatedFileName = 'HDFCSec_ContractNote_August_2026.pdf';
      simulatedPassword = targetPortfolio?.pan || 'ABCDE1234F';
    } else if (type === 'cams' || type === 'nsdl') {
      simulatedType = 'NSDL';
      simulatedFileName = 'NSDLe-CAS_112906552_JUL_2026.PDF';
      simulatedPassword = password || targetPortfolio?.pan || 'KLMNO9012P';
    } else if (type === 'schwab') {
      simulatedType = 'SCHWAB';
      simulatedFileName = 'CharlesSchwab_Equity_Awards_Activity_2026.csv';
      simulatedPassword = ''; // Schwab CSVs are unencrypted
      mime = 'text/csv';
    }

    setStatementType(simulatedType);
    setFileName(simulatedFileName);
    setPassword(simulatedPassword);
    
    // Create a real File instance representing the sample
    const sampleBlob = new Blob([`SAMPLE_${simulatedType}_STATEMENT_DATA`], { type: mime });
    const sampleFile = new File([sampleBlob], simulatedFileName, { type: mime });
    setSelectedFile(sampleFile);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setFileName(file.name);
      setErrorMessage(null);
      setResultMessage(null);
      setImportedAssetsSummary(null);
      
      const lower = file.name.toLowerCase();
      if (lower.includes('nsdl') || lower.includes('cdsl') || lower.includes('ecas')) {
        setStatementType('NSDL');
      } else if (lower.includes('zerodha') || lower.includes('tradebook')) {
        setStatementType('ZERODHA');
      } else if (lower.includes('hdfc')) {
        setStatementType('HDFC');
      } else if (lower.includes('cas') || lower.includes('cams') || lower.includes('kfintech')) {
        setStatementType('CAMS');
      } else if (lower.includes('schwab') || lower.includes('charles') || lower.includes('equity')) {
        setStatementType('SCHWAB');
      }
    }
  };

  

  const handleProcessImport = async () => {
    if (!selectedFile) {
      alert('Please select or upload a statement first.');
      return;
    }

    setIsProcessing(true);
    setResultMessage(null);
    setErrorMessage(null);
    setGateDetails(null);
    setImportedAssetsSummary(null);

    const panEntered = (password || targetPortfolio?.pan || 'KLMNO9012P').trim().toUpperCase();

    try {
      if (selectedFile) {
        const response: IngestionApiResponse = await MoneyMoneyApi.processStatementFile(selectedFile, {
          portfolioId: selectedPortfolioId,
          targetPan: panEntered,
          password: password || panEntered,
          broker: statementType,
        });

        if (response.success) {
          const count = response.data?.new_transactions_committed || response.new_transactions_committed || 0;
          setResultMessage(`Gate 1-4 Verification Passed! Reconciled ${count} new transactions into canonical ledger.`);
          setGateDetails(`Decrypted via PAN (${panEntered}) • Invariant check passed.`);
          setImportedAssetsSummary({ count, totalINR: 0 }); // Values will update live via Firebase

          onImportSuccess(selectedPortfolioId, count, [], panEntered);
        } else {
          let reason = response.rejection_reason || 'Invariant mismatch';
          if (response.discrepancy) {
            const d = response.discrepancy;
            if (d.field) reason += ` [Field: ${d.field}]`;
            if (d.expected !== undefined && d.actual !== undefined) {
              reason += ` (Expected: ${d.expected}, Actual: ${d.actual}, Δ: ${d.difference ?? 'N/A'})`;
            }
          }
          setErrorMessage(`Rejection at ${response.failed_gate || 'Validation Gate'}: ${reason}`);
        }
      }
    } catch (err: any) {
      setErrorMessage(`Ingestion error: ${err.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.98 }}
      transition={{ duration: 0.4 }}
      id="app-main-view" 
      className="space-y-5 max-w-4xl mx-auto"
    >
      <div className="card space-y-1.5 border-l-2 border-l-blue-500">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-extrabold text-zinc-100 flex items-center gap-2 tracking-tight">
            <FileUp className="w-5 h-5 text-blue-400" />
            <span>Statement & Ingestion Center</span>
          </h1>
          <div className="flex items-center gap-1.5 text-xs text-emerald-400 bg-emerald-950/40 px-2.5 py-1 rounded-full border border-emerald-800/40 font-mono">
            <Server className="w-3.5 h-3.5" />
            <span>Cloud Run Ingestion Active</span>
          </div>
        </div>
        <p className="text-xs text-zinc-400">
          Automated 4-gate ingestion pipeline for <strong>Zerodha ECN</strong>, <strong>HDFC Securities</strong>, <strong>CAMS/KFintech e-CAS</strong>, and <strong>Charles Schwab (US)</strong>.
        </p>
      </div>

      {/* Upload Card */}
      <div className="card space-y-5">
        
        {/* Step 1: Select Target Portfolio */}
        <div>
          <label className="block text-xs font-bold uppercase tracking-wider text-zinc-400 mb-2">
            1. Select Target Family Portfolio
          </label>
          <select
            value={selectedPortfolioId}
            onChange={(e) => setSelectedPortfolioId(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-bold text-zinc-200 focus:ring-1 focus:ring-blue-500"
          >
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.ownerName} — {p.name} (PAN: {p.pan})
              </option>
            ))}
          </select>
        </div>

        {/* Step 2: 1-Click Interactive Test Statements */}
        <div className="p-3.5 rounded-lg bg-zinc-900/60 border border-zinc-800 space-y-2.5">
          <span className="text-xs font-bold uppercase tracking-wider text-yellow-400 block">
            🚀 1-Click Test Ingestion Files (Click to load sample):
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => handleSimulateUpload('zerodha')}
              className="btn btn-outline text-xs font-bold justify-start py-2"
            >
              📄 Load Sample Zerodha Contract Note
            </button>
            <button
              type="button"
              onClick={() => handleSimulateUpload('hdfc')}
              className="btn btn-outline text-xs font-bold justify-start py-2"
            >
              📄 Load Sample HDFC Securities Note
            </button>
            <button
              type="button"
              onClick={() => handleSimulateUpload('cams')}
              className="btn btn-outline text-xs font-bold justify-start py-2"
            >
              📄 Load Sample CAMS/KFintech CAS PDF
            </button>
            <button
              type="button"
              onClick={() => handleSimulateUpload('schwab')}
              className="btn btn-outline text-xs font-bold justify-start py-2 text-blue-400 border-blue-800/40"
            >
              <Globe className="w-3.5 h-3.5" />
              <span>Load Sample Charles Schwab (US) CSV</span>
            </button>
          </div>
        </div>

        {/* Step 3: Drag & Drop Container */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept=".pdf,.csv"
          className="hidden"
        />
        <div 
          onClick={() => fileInputRef.current?.click()}
          className="border border-dashed border-zinc-700 hover:border-blue-500 rounded-xl p-6 text-center space-y-2 bg-zinc-900/60 cursor-pointer transition-colors"
        >
          {selectedFile ? (
            <UploadCloud className="w-10 h-10 text-emerald-400 mx-auto opacity-90 animate-bounce" />
          ) : (
            <FileText className="w-10 h-10 text-blue-400 mx-auto opacity-80" />
          )}
          <div>
            <div className="text-sm font-bold text-zinc-200">
              {fileName ? fileName : 'Click to select or drag & drop contract note, CAS PDF, or Schwab CSV'}
            </div>
            <div className="text-xs text-zinc-500 mt-0.5">
              Supports Zerodha ECN / Tradebook CSV, HDFC Sec, CAMS e-CAS, Charles Schwab
            </div>
          </div>
        </div>

        {/* Step 4: Password Decryption (If PDF) */}
        {statementType !== 'SCHWAB' && (
          <div>
            <label className="block text-xs font-bold text-zinc-400 mb-1.5 flex items-center gap-1.5">
              <Lock className="w-3.5 h-3.5 text-yellow-400" />
              <span>PDF Decryption Password (User PAN or DOB)</span>
            </label>
            <input
              type="text"
              placeholder={`e.g. ${targetPortfolio?.pan || 'KLMNO9012P'}`}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm font-mono text-zinc-100 uppercase focus:ring-1 focus:ring-blue-500"
            />
          </div>
        )}

        {/* Advisor Read-Only Notice */}
        {!permissions.canUploadStatements && (
          <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium flex items-center gap-2">
            <Lock className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              <strong>Advisor Mode (Read-Only)</strong>: Statement upload and ledger modification are restricted to Family Administrators.
            </span>
          </div>
        )}

        {/* Submit Action */}
        <button
          onClick={handleProcessImport}
          disabled={isProcessing || !permissions.canUploadStatements}
          className={`w-full btn ${!permissions.canUploadStatements ? 'btn-secondary opacity-60 cursor-not-allowed text-zinc-400' : 'btn-primary'} py-3 text-sm font-extrabold`}
        >
          {isProcessing ? (
            <span className="flex items-center justify-center gap-2">
              <Sparkles className="w-4 h-4 animate-spin text-blue-600" />
              Executing 4-Gate Fail-Closed Pipeline...
            </span>
          ) : !permissions.canUploadStatements ? (
            <span className="flex items-center justify-center gap-2">
              <Lock className="w-4 h-4 text-zinc-400" />
              Upload Restricted (Advisor Read-Only Mode)
            </span>
          ) : (
            <span className="flex items-center justify-center gap-2">
              <ShieldCheck className="w-4 h-4 text-blue-600" />
              Process & Reconcile Statement
            </span>
          )}
        </button>

            {/* Success Alert & 1-Click Proceed Buttons */}
        {resultMessage && (
          <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/50 text-emerald-300 font-bold text-xs space-y-3 shadow-lg">
            <div className="flex items-start gap-2.5">
              <CheckCircle className="w-5 h-5 shrink-0 mt-0.5 text-emerald-400" />
              <div>
                <div className="text-sm font-extrabold text-emerald-200">{resultMessage}</div>
                {gateDetails && (
                  <div className="text-xs font-normal text-emerald-300/80 mt-1">
                    {gateDetails}
                  </div>
                )}
                {importedAssetsSummary && (
                  <div className="mt-2 text-xs font-bold text-emerald-400 bg-emerald-900/30 px-2.5 py-1 rounded-md inline-block border border-emerald-800/40 font-mono">
                    ✓ Reconciled {importedAssetsSummary.count} assets • Net Value: ₹{importedAssetsSummary.totalINR.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </div>
                )}
              </div>
            </div>

            {/* Action Buttons to View Updated Vault */}
            <div className="pt-2 border-t border-emerald-800/40 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={onNavigateToDashboard}
                className="btn btn-primary bg-emerald-600 hover:bg-emerald-500 text-white font-extrabold text-xs px-4 py-2.5 flex items-center gap-2 shadow-md"
              >
                <LayoutDashboard className="w-4 h-4" />
                <span>Go to Dashboard & See Reconciled Total</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={onNavigateToHoldings}
                className="btn btn-outline text-emerald-300 border-emerald-700/60 hover:bg-emerald-900/30 font-extrabold text-xs px-4 py-2.5 flex items-center gap-2"
              >
                <Wallet className="w-4 h-4 text-emerald-400" />
                <span>View Full Holdings List</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}

        {/* Error Alert */}
        {errorMessage && (
          <div className="p-3.5 rounded-lg bg-red-950/20 border border-red-500/40 text-red-300 font-bold text-xs flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-red-400" />
            <span>{errorMessage}</span>
          </div>
        )}

      </div>

    </motion.div>
  );
};
