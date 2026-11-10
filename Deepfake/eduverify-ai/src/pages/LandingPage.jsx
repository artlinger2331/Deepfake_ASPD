import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Lock, BrainCircuit, Users, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';
import './LandingPage.css';

const LandingPage = () => {
  return (
    <div className="page-container container landing-container">
      <motion.div 
        className="hero-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="hero-icon-wrapper">
          <ShieldCheck size={48} className="hero-icon" />
        </div>
        
        <h1 className="hero-title">
          EduVerify AI <br />
          <span className="hero-subtitle">Assignment Verification Assistant</span>
        </h1>
        
        <p className="hero-description">
          Upload images of student assignments to get an explainable AI-assisted report. 
          This tool provides <span className="font-semibold">decision support for teachers</span>, it does not definitively prove misconduct.
        </p>

        <div className="hero-actions">
          <Link to="/upload" className="btn btn-primary btn-lg">
            Start Verification
            <ArrowRight size={18} />
          </Link>
          <a href="#how-it-works" className="btn btn-outline btn-lg">
            How it works
          </a>
        </div>
      </motion.div>

      <motion.div 
        className="trust-indicators"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3, duration: 0.5 }}
      >
        <div className="trust-item">
          <Lock size={24} className="trust-icon" />
          <span className="trust-text">Privacy-first</span>
        </div>
        <div className="trust-item">
          <BrainCircuit size={24} className="trust-icon" />
          <span className="trust-text">Explainable AI</span>
        </div>
        <div className="trust-item">
          <Users size={24} className="trust-icon" />
          <span className="trust-text">Designed for educators</span>
        </div>
      </motion.div>
    </div>
  );
};

export default LandingPage;
