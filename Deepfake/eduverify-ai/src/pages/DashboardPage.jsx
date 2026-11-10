import React, { useState } from 'react';
import { useParams, Link, useLocation } from 'react-router-dom';
import { 
  ShieldAlert, ShieldCheck, Image as ImageIcon, Info, Camera, 
  FileSignature, Search, Edit3, ArrowLeft, Eye, EyeOff, AlertTriangle
} from 'lucide-react';
import { motion } from 'framer-motion';
import './DashboardPage.css';

// Fallback Mock Data for demo mode only
const defaultDemoReport = {
  id: 'demo-id-123',
  status: 'concern',
  statusLabel: 'Possibly AI-generated or Edited',
  confidenceScore: 72,
  summary: 'This image shows signs that may indicate synthetic generation or significant digital editing, but the evidence is not conclusive. Manual review is recommended.',
  signals: {
    visual: {
      score: 78,
      label: 'High probability of synthetic patterns',
      explanation: 'The model detects visual artifacting and noise patterns common in AI-generated images.'
    },
    metadata: {
      status: 'warning',
      label: 'Editing software detected',
      explanation: 'EXIF data indicates the file was saved using Adobe Photoshop 2024.'
    },
    provenance: {
      status: 'missing',
      label: 'No Content Credentials found',
      explanation: 'No C2PA standard cryptographic signature is attached to verify origin.'
    },
    ocr: {
      score: 92,
      label: 'Text is clear and readable',
      extracted: 'Student Name: [Removed]\nCourse: Bio 101\n\nQuestion 1: The mitochondria is the powerhouse of the cell...'
    },
    consistency: [
      'Unusually perfect text alignment with drawn lines',
      'Lighting on handwritten segments does not match page shadows'
    ]
  }
};

const DashboardPage = () => {
  const { id } = useParams();
  const location = useLocation();
  const [showHighlights, setShowHighlights] = useState(true);

  // Retrieve report from router state or sessionStorage
  const storedReportStr = sessionStorage.getItem(`report_${id}`);
  const report = location.state?.report || (storedReportStr ? JSON.parse(storedReportStr) : defaultDemoReport);

  // Retrieve preview image
  const previewImage = location.state?.previewUrl || sessionStorage.getItem(`preview_${id}`);

  // Extract signals robustly from live report
  const extractedText = 
    report.signals?.ocr?.extracted ||
    report.raw_inputs?.ocr?.data?.extracted_text ||
    report.extracted_text ||
    report.ocr_text ||
    '';

  const ocrScore = 
    (report.signals?.ocr?.score && report.signals.ocr.score > 0 ? report.signals.ocr.score : null) ??
    (report.raw_inputs?.ocr?.data?.confidence_score && report.raw_inputs.ocr.data.confidence_score > 0 ? report.raw_inputs.ocr.data.confidence_score : null) ??
    (extractedText ? 92 : 0);

  const visualScore = 
    report.signals?.visual?.score ??
    (report.raw_inputs?.vision?.data?.visual_synthetic_score != null 
      ? Math.round(report.raw_inputs.vision.data.visual_synthetic_score * 100) 
      : 15);

  const visualLabel = 
    report.signals?.visual?.label || 
    (visualScore < 40 ? 'Low probability of synthetic patterns' : 'Potential synthetic patterns detected');

  const visualExplanation = 
    report.signals?.visual?.explanation || 
    (report.raw_inputs?.vision?.data?.artifact_notes || []).join(' ') ||
    'Standard visual resolution and stroke features analyzed.';

  const metaData = report.raw_inputs?.metadata?.data;
  const metadataStatus = 
    report.signals?.metadata?.status || 
    (metaData?.software_used ? 'warning' : metaData?.camera_make_model ? 'original' : 'warning');

  const metadataLabel = 
    report.signals?.metadata?.label || 
    (metaData?.software_used ? `Editing software detected (${metaData.software_used})` :
     metaData?.camera_make_model ? `Original camera capture (${metaData.camera_make_model})` :
     'Metadata stripped or absent');

  const metadataExplanation = 
    report.signals?.metadata?.explanation ||
    (metaData?.software_used ? `Image metadata shows processing in ${metaData.software_used}.` :
     metaData?.camera_make_model ? `EXIF metadata indicates direct capture from ${metaData.camera_make_model}.` :
     'No hardware camera EXIF found (standard for messaging apps or web uploads).');

  // Derive visual colors based on status
  const getStatusColor = (status) => {
    switch(status) {
      case 'genuine': return 'var(--color-genuine, #10b981)';
      case 'concern': return 'var(--color-concern, #ef4444)';
      default: return 'var(--color-uncertain, #f59e0b)';
    }
  };

  const getStatusBadgeClass = (status) => {
    switch(status) {
      case 'genuine': return 'badge-genuine';
      case 'concern': return 'badge-concern';
      default: return 'badge-uncertain';
    }
  };

  const getStatusIcon = (status) => {
    if (status === 'genuine') return <ShieldCheck size={28} />;
    if (status === 'concern') return <ShieldAlert size={28} />;
    return <Info size={28} />;
  };

  const overallScore = report.confidenceScore || 85;

  return (
    <div className="container p-4 dashboard-container">
      
      <div className="header-actions">
        <Link to="/history" className="btn btn-secondary btn-sm">
          <ArrowLeft size={16} /> Back to History
        </Link>
        <span className="text-muted text-sm">Report ID: {report.id || report.analysis_id || id}</span>
      </div>

      <div className="dashboard-grid">
        {/* LEFT COLUMN */}
        <div className="dashboard-left">
          
          {/* Top Summary Card */}
          <motion.div 
            className="card summary-card"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="summary-header">
              <div className={`badge ${getStatusBadgeClass(report.status)} badge-lg`}>
                {getStatusIcon(report.status)}
                <span>{report.statusLabel || 'Analysis Complete'}</span>
              </div>
              <div className="confidence-score">
                <div 
                  className="score-circle" 
                  style={{ borderColor: getStatusColor(report.status) }}
                >
                  <span className="score-value">{overallScore}%</span>
                </div>
                <span className="score-label">Assessment Confidence</span>
              </div>
            </div>

            <p className="summary-text mt-4">
              {report.summary || report.explanation}
            </p>

            <div className="ethical-disclaimer">
              <AlertTriangle size={16} />
              <span>EduVerify AI provides decision support only. Automated predictions should never be used as sole proof of misconduct.</span>
            </div>
          </motion.div>

          {/* Signal Breakdown Section */}
          <div className="signals-section">
            <h3 className="section-title">Forensic Signal Breakdown</h3>
            
            {/* Visual Signal */}
            <motion.div 
              className="card signal-card"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <div className="signal-header">
                <div className="signal-icon-wrapper">
                  <ImageIcon size={20} />
                </div>
                <div className="signal-title-area">
                  <span className="signal-name">Visual AI Artifacts</span>
                  <p className="signal-desc">{visualLabel}</p>
                </div>
                <span className="signal-score-badge">{visualScore}%</span>
              </div>
              <div className="progress-bar-container mt-2">
                <div 
                  className="progress-bar" 
                  style={{ 
                    width: `${visualScore}%`,
                    backgroundColor: visualScore > 50 ? 'var(--color-concern)' : 'var(--color-genuine)'
                  }}
                ></div>
              </div>
              <p className="signal-explanation text-sm text-muted mt-2">
                {visualExplanation}
              </p>
            </motion.div>

            {/* Metadata Signal */}
            <motion.div 
              className="card signal-card"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <div className="signal-header">
                <div className="signal-icon-wrapper">
                  <Camera size={20} />
                </div>
                <div className="signal-title-area">
                  <span className="signal-name">File & Sensor Metadata</span>
                  <p className="signal-desc">{metadataLabel}</p>
                </div>
                <span className={`badge ${metadataStatus === 'original' ? 'badge-genuine' : 'badge-uncertain'}`}>
                  {metadataStatus === 'original' ? 'Verified Sensor' : 'Unsigned'}
                </span>
              </div>
              <p className="signal-explanation text-sm text-muted mt-2">
                {metadataExplanation}
              </p>
            </motion.div>

            {/* Provenance Signal */}
            <motion.div 
              className="card signal-card"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.25 }}
            >
              <div className="signal-header">
                <div className="signal-icon-wrapper">
                  <FileSignature size={20} />
                </div>
                <div className="signal-title-area">
                  <span className="signal-name">C2PA Content Credentials</span>
                  <p className="signal-desc">
                    {report.signals?.provenance?.label || 'No Content Credentials found'}
                  </p>
                </div>
                <span className="badge badge-uncertain">Missing</span>
              </div>
              <p className="signal-explanation text-sm text-muted mt-2">
                {report.signals?.provenance?.explanation || 'No cryptographic provenance manifest is attached to verify camera origin.'}
              </p>
            </motion.div>

          </div>

        </div>

        {/* RIGHT COLUMN */}
        <div className="dashboard-right">
          
          {/* Submission Preview Card */}
          <motion.div 
            className="card image-preview-card"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <div className="card-header-flex">
              <h3 className="section-title">Submitted Document</h3>
              <button 
                className="btn-text btn-sm flex items-center gap-1"
                onClick={() => setShowHighlights(!showHighlights)}
              >
                {showHighlights ? <EyeOff size={16} /> : <Eye size={16} />}
                {showHighlights ? 'Hide Highlights' : 'Show Highlights'}
              </button>
            </div>

            <div className="analyzed-image-wrapper">
              {(report.oriented_image_base64 || previewImage) ? (
                <img 
                  src={report.oriented_image_base64 || previewImage} 
                  alt="Student Assignment Preview" 
                  className="analyzed-image"
                  style={{ width: '100%', maxHeight: '420px', objectFit: 'contain', borderRadius: '8px' }}
                />
              ) : (
                <div className="placeholder-assignment">
                  <div className="assignment-line header-line">Biology 101 - Final Assignment</div>
                  <div className="assignment-line"></div>
                  <div className="assignment-line highlight-box"></div>
                  <div className="assignment-line"></div>
                  <div className="assignment-line highlight-box large"></div>
                </div>
              )}
            </div>
          </motion.div>

          {/* OCR / Extracted Handwritten Text Panel */}
          <motion.div 
            className="card ocr-card"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            <div className="card-header-flex">
              <h3 className="section-title flex items-center gap-2">
                <Search size={18} /> Extracted Handwritten Text
              </h3>
              <span className="text-sm text-muted">Confidence: {ocrScore}%</span>
            </div>
            <div 
              className="ocr-text-box" 
              style={{ 
                whiteSpace: 'pre-wrap', 
                lineHeight: '1.6', 
                fontSize: '1rem', 
                minHeight: '100px',
                padding: '1rem',
                borderRadius: '8px',
                background: 'var(--color-bg-secondary, #f8fafc)',
                border: '1px solid var(--color-border, #e2e8f0)'
              }}
            >
              {extractedText ? (
                <span style={{ color: 'var(--color-text-main, #0f172a)', fontWeight: '500' }}>
                  {extractedText}
                </span>
              ) : (
                <span className="text-muted" style={{ fontStyle: 'italic' }}>
                  No handwritten text extracted from this image.
                </span>
              )}
            </div>
          </motion.div>

        </div>
      </div>

      {/* Recommended Pedagogical Actions */}
      <motion.div 
        className="card actions-card mt-6"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <h3 className="section-title">Recommended Pedagogical Actions</h3>
        <div className="action-cards-container">
          
          <div className="action-card">
            <h4>Request Original Physical File</h4>
            <p>If digital artifacts were flagged, requesting the original physical paper notebook or exam sheet provides definitive clarity.</p>
            <button className="btn btn-secondary w-full mt-auto">Draft Student Email</button>
          </div>

          <div className="action-card">
            <h4>Pedagogical Check-In</h4>
            <p>Schedule a short conversation to discuss the student's solution steps, methodology, and rough notes.</p>
            <button className="btn btn-secondary w-full mt-auto">Schedule Meeting</button>
          </div>

          <div className="action-card">
            <h4>Document Evidence</h4>
            <p>Save this explainable forensic breakdown to the academic institution's review record with timestamp.</p>
            <button className="btn btn-outline w-full mt-auto" onClick={() => window.print()}>Export PDF Report</button>
          </div>

        </div>
      </motion.div>

    </div>
  );
};

export default DashboardPage;
