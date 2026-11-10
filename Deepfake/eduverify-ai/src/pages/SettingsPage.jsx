import React, { useState } from 'react';
import { Save, Shield, Clock, Layers, FileText, Lock } from 'lucide-react';
import './SettingsPage.css';

const SettingsPage = () => {
  const [settings, setSettings] = useState({
    requireDisclaimer: true,
    deleteAfter24H: true,
    allowBatchUpload: false,
    policyText: 'Students are expected to submit original work. The use of generative AI must be declared and cited appropriately. Unauthorized use of AI to generate academic submissions constitutes academic misconduct.'
  });

  const handleToggle = (key) => {
    setSettings(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSave = () => {
    // Simulate save
    alert('Settings saved successfully.');
  };

  return (
    <div className="container p-4 max-w-3xl">
      <div className="settings-header">
        <h2>Settings & Policies</h2>
        <p className="text-muted">Configure how EduVerify AI operates for your classroom.</p>
      </div>

      <div className="settings-section card">
        <h3 className="section-title">Application Preferences</h3>
        
        <div className="setting-item">
          <div className="setting-info">
            <Shield size={20} className="setting-icon" />
            <div>
              <h4>Require disclaimer on every report</h4>
              <p className="text-sm text-muted">Ensures the "Decision Support Only" disclaimer is shown.</p>
            </div>
          </div>
          <label className="toggle-switch">
            <input 
              type="checkbox" 
              checked={settings.requireDisclaimer} 
              onChange={() => handleToggle('requireDisclaimer')}
            />
            <span className="slider round"></span>
          </label>
        </div>

        <div className="setting-item">
          <div className="setting-info">
            <Clock size={20} className="setting-icon" />
            <div>
              <h4>Delete uploaded images after 24 hours</h4>
              <p className="text-sm text-muted">Automatically purges files from local storage for privacy.</p>
            </div>
          </div>
          <label className="toggle-switch">
            <input 
              type="checkbox" 
              checked={settings.deleteAfter24H} 
              onChange={() => handleToggle('deleteAfter24H')}
            />
            <span className="slider round"></span>
          </label>
        </div>

        <div className="setting-item">
          <div className="setting-info">
            <Layers size={20} className="setting-icon" />
            <div>
              <h4>Allow batch upload</h4>
              <p className="text-sm text-muted">Enable uploading multiple pages or assignments at once.</p>
            </div>
          </div>
          <label className="toggle-switch">
            <input 
              type="checkbox" 
              checked={settings.allowBatchUpload} 
              onChange={() => handleToggle('allowBatchUpload')}
            />
            <span className="slider round"></span>
          </label>
        </div>
      </div>

      <div className="settings-section card mt-6">
        <div className="setting-header-flex">
          <FileText size={20} className="setting-icon text-primary" />
          <h3 className="section-title" style={{marginBottom: 0}}>Institutional Academic Integrity Policy</h3>
        </div>
        <p className="text-sm text-muted mb-4">
          This text will be appended to exported reports as your classroom's standard.
        </p>
        <textarea 
          className="policy-textarea"
          value={settings.policyText}
          onChange={(e) => setSettings({...settings, policyText: e.target.value})}
          rows={5}
        />
      </div>

      <div className="privacy-statement card mt-6">
        <Lock size={20} className="text-primary flex-shrink-0" />
        <div>
          <h4>Privacy Statement</h4>
          <p className="text-sm text-muted">
            Uploaded images are processed locally or on secure servers and are <strong>not used to train public AI models</strong>. Your students' data remains private.
          </p>
        </div>
      </div>

      <div className="settings-actions mt-6">
        <button className="btn btn-primary" onClick={handleSave}>
          <Save size={18} /> Save Settings
        </button>
      </div>

    </div>
  );
};

export default SettingsPage;
