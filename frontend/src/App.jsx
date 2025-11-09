import React, { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import CompanyView from './pages/CompanyView'
import Header from './components/Header'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <Header />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/company/:ticker" element={<CompanyView />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}

export default App
