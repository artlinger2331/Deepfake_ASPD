import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UploadCloud, Image as ImageIcon, AlertTriangle, X, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import './UploadPage.css';

const UploadPage = () => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [errorMessage, setErrorMessage] = useState(null);
  const navigate = useNavigate();

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const processFile = (file) => {
    if (file && (file.type.startsWith('image/') || /\.(jpg|jpeg|png|webp|bmp)$/i.test(file.name))) {
      setSelectedFile(file);
      setErrorMessage(null);
      const reader = new FileReader();
      reader.onload = (e) => {
        setPreviewUrl(e.target.result);
      };
      reader.readAsDataURL(file);
    } else {
      setErrorMessage("Please select a valid image file (JPG, PNG, WebP).");
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const startAnalysis = async () => {
    if (!selectedFile) return;
    setIsAnalyzing(true);
    setProgress(15);
    setErrorMessage(null);

    // Dynamic progress ticker while server runs GPU multimodal model
    const progressInterval = setInterval(() => {
      setProgress((prev) => (prev < 85 ? prev + Math.floor(Math.random() * 8) + 4 : prev));
    }, 350);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const response = await fetch('/api/v1/analyze', {
        method: 'POST',
        body: formData,
      });

      clearInterval(progressInterval);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Server returned ${response.status}: ${errorText}`);
      }

      const reportData = await response.json();
      setProgress(100);

      // Save report and preview into storage
      const reportId = reportData.id || reportData.analysis_id || `EV-${Date.now()}`;
      if (previewUrl) {
        sessionStorage.setItem(`preview_${reportId}`, previewUrl);
      }
      sessionStorage.setItem(`report_${reportId}`, JSON.stringify(reportData));

      // Append to history list in localStorage
      try {
        const history = JSON.parse(localStorage.getItem('eduverify_history') || '[]');
        const newHistoryItem = {
          id: reportId,
          timestamp: new Date().toISOString(),
          status: reportData.status,
          statusLabel: reportData.statusLabel,
          confidenceScore: reportData.confidenceScore,
          wordCount: reportData.signals?.ocr?.extracted ? reportData.signals.ocr.extracted.split(' ').length : 0,
          previewUrl: previewUrl || null
        };
        localStorage.setItem('eduverify_history', JSON.stringify([newHistoryItem, ...history.slice(0, 19)]));
      } catch (err) {
        console.warn('Could not save to history storage:', err);
      }

      setTimeout(() => {
        navigate(`/analysis/${reportId}`, {
          state: {
            report: reportData,
            previewUrl: previewUrl
          }
        });
      }, 400);

    } catch (error) {
      clearInterval(progressInterval);
      setIsAnalyzing(false);
      setProgress(0);
      console.error('Analysis failed:', error);
      setErrorMessage(`Failed to complete analysis. Ensure the backend is running. Details: ${error.message}`);
    }
  };

  return (
    <div className="container p-4 max-w-3xl">
      <div className="upload-header">
        <h2>Verify Assignment</h2>
        <p className="text-muted">Upload a photograph or scan of the student's submission to run forensic handwriting and visual verification.</p>
      </div>

      <div className="privacy-notice">
        <AlertTriangle size={20} className="notice-icon" />
        <div className="notice-content">
          <h4>Privacy Notice</h4>
          <p>Please ensure you <strong>do not upload images</strong> that contain student names, faces, or personal identifiable information.</p>
        </div>
      </div>

      {errorMessage && (
        <div className="card" style={{ borderColor: 'var(--color-concern, #ef4444)', marginBottom: '1.5rem', background: 'rgba(239, 68, 68, 0.08)' }}>
          <p style={{ color: 'var(--color-concern, #ef4444)', fontWeight: '500', margin: 0 }}>
            {errorMessage}
          </p>
        </div>
      )}

      {!selectedFile ? (
        <div
          className={`drop-zone card ${dragActive ? 'drag-active' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            type="file"
            id="file-upload"
            className="file-input"
            accept="image/jpeg, image/png, image/webp"
            onChange={handleChange}
          />
          <label htmlFor="file-upload" className="drop-zone-content">
            <UploadCloud size={48} className="upload-icon" />
            <h3 className="upload-title">Drag & drop an image here</h3>
            <p className="upload-subtitle">or click to browse from your computer</p>
            <span className="upload-formats">Supported formats: JPG, PNG, WebP (Max 15MB)</span>
            <div className="btn btn-primary mt-4">Browse Files</div>
          </label>
        </div>
      ) : (
        <motion.div
          className="file-preview-card card"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
        >
          <div className="preview-header">
            <div className="file-info">
              <div className="file-icon-wrapper">
                <ImageIcon size={24} />
              </div>
              <div className="file-details">
                <span className="file-name">{selectedFile.name}</span>
                <span className="file-size">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
            </div>
            {!isAnalyzing && (
              <button 
                className="btn-icon" 
                onClick={() => {
                  setSelectedFile(null);
                  setPreviewUrl(null);
                }}
              >
                <X size={20} />
              </button>
            )}
          </div>

          <div className="preview-image-container">
            {previewUrl && (
              <img src={previewUrl} alt="Preview" className="preview-image" />
            )}
          </div>

          {isAnalyzing ? (
            <div className="analysis-progress">
              <div className="progress-header">
                <span className="progress-title flex items-center gap-2">
                  <Loader2 className="animate-spin" size={16} /> Running GPU Forensic Models...
                </span>
                <span className="progress-percentage">{progress}%</span>
              </div>
              <div className="progress-bar-container">
                <motion.div
                  className="progress-bar"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                ></motion.div>
              </div>
              <p className="progress-desc">Extracting handwriting with Qwen2-VL, checking EXIF metadata, and scanning visual stroke features...</p>
            </div>
          ) : (
            <div className="preview-actions">
              <button
                className="btn btn-outline"
                onClick={() => {
                  setSelectedFile(null);
                  setPreviewUrl(null);
                }}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={startAnalysis}
              >
                Start Analysis
              </button>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
};

export default UploadPage;
