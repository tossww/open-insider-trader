import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { formatDistanceToNow, format } from 'date-fns'

function Dashboard() {
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    minScore: null,
    minValue: null
  })
  const navigate = useNavigate()

  useEffect(() => {
    fetchTransactions()
  }, [filters])

  const fetchTransactions = async () => {
    try {
      setLoading(true)
      const params = {}
      if (filters.minScore !== null) params.min_score = filters.minScore
      if (filters.minValue !== null) params.min_value = filters.minValue

      const response = await axios.get('/api/transactions/feed', { params })
      setTransactions(response.data)
    } catch (error) {
      console.error('Error fetching transactions:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRowClick = (ticker) => {
    // Don't navigate if user is selecting text
    const selection = window.getSelection()
    if (selection && selection.toString().length > 0) {
      return
    }
    navigate(`/company/${ticker}`)
  }

  const getScoreBadge = (score, category) => {
    if (!score) return null

    const colors = {
      strong_buy: 'bg-green-100 text-green-800',
      watch: 'bg-yellow-100 text-yellow-800',
      weak: 'bg-gray-100 text-gray-800',
      ignore: 'bg-gray-50 text-gray-600'
    }

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${colors[category] || 'bg-gray-100 text-gray-800'}`}>
        Score: {score}
      </span>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Insider Trading Feed
        </h1>
        <p className="text-gray-600">
          Recent buy transactions with conviction signals
        </p>
      </div>

      {/* Filters */}
      <div className="mb-6 flex space-x-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Min Score
          </label>
          <select
            value={filters.minScore || ''}
            onChange={(e) => setFilters({ ...filters, minScore: e.target.value ? parseInt(e.target.value) : null })}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All</option>
            <option value="3">≥3 (Weak)</option>
            <option value="5">≥5 (Watch)</option>
            <option value="7">≥7 (Strong Buy)</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Min Value
          </label>
          <select
            value={filters.minValue || ''}
            onChange={(e) => setFilters({ ...filters, minValue: e.target.value ? parseInt(e.target.value) : null })}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All</option>
            <option value="100000">$100K+</option>
            <option value="500000">$500K+</option>
            <option value="1000000">$1M+</option>
          </select>
        </div>
      </div>

      {/* Transaction Feed */}
      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : (
        <div className="bg-white shadow-sm rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Company
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Insider
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Trade Value
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Signal
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {transactions.map((txn) => (
                <tr
                  key={txn.id}
                  onClick={() => handleRowClick(txn.ticker)}
                  className="hover:bg-gray-50 cursor-pointer transition"
                >
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-blue-600">${txn.ticker}</span>
                      <span className="text-xs text-gray-500">{txn.company_name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="text-sm text-gray-900">{txn.insider_name}</span>
                      <span className="text-xs text-gray-500">{txn.insider_title || 'N/A'}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${txn.total_value?.toLocaleString() || 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <div className="flex flex-col">
                      <span className="text-gray-900">{format(new Date(txn.filing_date), 'yyyy-MM-dd HH:mm')}</span>
                      <span className="text-xs text-gray-500">{formatDistanceToNow(new Date(txn.filing_date), { addSuffix: true })}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getScoreBadge(txn.signal_score, txn.threshold_category)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {transactions.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              No transactions found matching your filters.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default Dashboard
