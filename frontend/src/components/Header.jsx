import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'

function Header() {
  const [searchTicker, setSearchTicker] = useState('')
  const navigate = useNavigate()

  const handleSearch = (e) => {
    e.preventDefault()
    if (searchTicker.trim()) {
      navigate(`/company/${searchTicker.toUpperCase()}`)
      setSearchTicker('')
    }
  }

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <a href="/" className="text-2xl font-bold text-gray-900">
              Open Insider Trader
            </a>
          </div>

          <form onSubmit={handleSearch} className="flex items-center space-x-2">
            <input
              type="text"
              placeholder="Search ticker..."
              value={searchTicker}
              onChange={(e) => setSearchTicker(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              Search
            </button>
          </form>
        </div>
      </div>
    </header>
  )
}

export default Header
