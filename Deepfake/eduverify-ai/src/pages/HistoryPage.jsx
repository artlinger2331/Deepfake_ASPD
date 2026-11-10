import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, Filter, Download, ShieldCheck, ShieldAlert, Info, Edit2 } from 'lucide-react';
import './HistoryPage.css';

const MOCK_HISTORY = [
  { id: 'HT-9812', date: 'Oct 09, 2026', name: 'Bio 101 - Final Essay', status: 'concern', statusText: 'Possibly AI-generated' },
  { id: 'HT-9813', date: 'Oct 08, 2026', name: 'Math Quiz 3 - John D.', status: 'genuine', statusText: 'Likely genuine' },
  { id: 'HT-9814', date: 'Oct 05, 2026', name: 'History Paper - Week 4', status: 'uncertain', statusText: 'Uncertain' },
  { id: 'HT-9815', date: 'Oct 01, 2026', name: 'Physics Lab Report', status: 'genuine', statusText: 'Likely genuine' },
];

const HistoryPage = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState('all');

  const getStatusIcon = (status) => {
    if (status === 'genuine') return <ShieldCheck size={16} className="text-emerald-600" />;
    if (status === 'concern') return <ShieldAlert size={16} className="text-amber-600" />;
    return <Info size={16} className="text-slate-600" />;
  };

  const getStatusBadgeClass = (status) => {
    switch(status) {
      case 'genuine': return 'badge-genuine';
      case 'concern': return 'badge-concern';
      default: return 'badge-uncertain';
    }
  };

  const filteredHistory = MOCK_HISTORY.filter(item => {
    const matchesSearch = item.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filter === 'all' || item.status === filter;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="container p-4 max-w-4xl">
      <div className="page-header">
        <div>
          <h2 className="text-2xl font-semibold mb-2">Analysis History</h2>
          <p className="text-muted">Review past assignments and export reports.</p>
        </div>
        <button className="btn btn-outline">
          <Download size={18} /> Export All as PDF
        </button>
      </div>

      <div className="controls-bar card">
        <div className="search-box">
          <Search size={18} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search by assignment name..." 
            className="search-input"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        
        <div className="filter-box">
          <Filter size={18} className="text-muted" />
          <select 
            className="filter-select"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">All Statuses</option>
            <option value="genuine">Likely Genuine</option>
            <option value="concern">Possible Concerns</option>
            <option value="uncertain">Uncertain</option>
          </select>
        </div>
      </div>

      <div className="history-list card">
        <div className="table-responsive">
          <table className="history-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Assignment Name</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredHistory.map((item) => (
                <tr key={item.id}>
                  <td className="text-muted">{item.date}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{item.name}</span>
                      <button className="btn-icon-small" title="Edit Name">
                        <Edit2 size={14} />
                      </button>
                    </div>
                    <div className="text-xs text-muted">ID: {item.id}</div>
                  </td>
                  <td>
                    <span className={`badge ${getStatusBadgeClass(item.status)}`}>
                      {getStatusIcon(item.status)} {item.statusText}
                    </span>
                  </td>
                  <td className="text-right">
                    <Link to={`/analysis/${item.id}`} className="btn btn-secondary btn-sm">
                      View Report
                    </Link>
                  </td>
                </tr>
              ))}
              
              {filteredHistory.length === 0 && (
                <tr>
                  <td colSpan="4" className="text-center p-8 text-muted">
                    No records found matching your filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      
    </div>
  );
};

export default HistoryPage;
