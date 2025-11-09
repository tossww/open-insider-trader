import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import axios from 'axios'
import { format, formatDistanceToNow } from 'date-fns'

function CompanyView() {
  const { ticker } = useParams()
  const [company, setCompany] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedInsider, setSelectedInsider] = useState(null)

  useEffect(() => {
    fetchCompanyData()
  }, [ticker])

  const fetchCompanyData = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await axios.get(`/api/companies/${ticker}`)
      setCompany(response.data)
    } catch (error) {
      console.error('Error fetching company:', error)
      setError(error.response?.data?.detail || 'Failed to load company data')
    } finally {
      setLoading(false)
    }
  }

  const getPerformanceColor = (winRate, alpha) => {
    if (!winRate || !alpha) return 'text-gray-500'
    if (winRate > 0.7 && alpha > 0.1) return 'text-green-600'
    if (winRate > 0.6 && alpha > 0.05) return 'text-yellow-600'
    return 'text-gray-600'
  }

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
      {/* Company Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          ${company.ticker} - {company.name}
        </h1>
        <div className="mt-2 flex space-x-6 text-sm text-gray-600">
          <span>{company.total_insiders} Insiders</span>
          <span>{company.total_transactions} Transactions</span>
          <span className="text-green-600">
            ${(company.recent_buy_value / 1000000).toFixed(1)}M Buys (90d)
          </span>
          <span className="text-red-600">
            ${(company.recent_sell_value / 1000000).toFixed(1)}M Sells (90d)
          </span>
        </div>
      </div>

      {/* Insider Performance Table */}
      <div className="bg-white shadow-sm rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Insider Activity</h2>
        </div>

        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Insider
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Buys
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Sells
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Win Rate (3m)
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Avg Return
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Alpha vs SPY
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                Latest Trade
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {company.insiders.map((insider) => (
              <tr
                key={insider.id}
                onClick={() => setSelectedInsider(insider.id)}
                className={`hover:bg-gray-50 cursor-pointer transition ${getPerformanceColor(insider.win_rate_3m, insider.alpha_vs_spy)}`}
              >
                <td className="px-6 py-4">
                  <div className="flex flex-col">
                    <span className="text-sm font-medium text-gray-900">{insider.name}</span>
                    <span className="text-xs text-gray-500">{insider.title || 'N/A'}</span>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  {insider.total_buys}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  {insider.total_sells}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  {insider.win_rate_3m ? `${(insider.win_rate_3m * 100).toFixed(1)}%` : 'N/A'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm">
                  {insider.avg_return ? `${(insider.avg_return * 100).toFixed(2)}%` : 'N/A'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                  {insider.alpha_vs_spy ? `${(insider.alpha_vs_spy * 100).toFixed(2)}%` : 'N/A'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {insider.latest_filing_date ? (
                    <div>
                      <div className="text-gray-900">${insider.latest_trade_value?.toLocaleString()}</div>
                      <div className="text-xs text-gray-900">
                        {format(new Date(insider.latest_filing_date), 'yyyy-MM-dd HH:mm')}
                      </div>
                      <div className="text-xs text-gray-500">
                        {formatDistanceToNow(new Date(insider.latest_filing_date), { addSuffix: true })}
                      </div>
                    </div>
                  ) : 'N/A'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {company.insiders.length === 0 && (
          <div className="text-center py-12 text-gray-500">
            No insider data available for this company.
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center space-x-6 text-sm">
        <span className="flex items-center">
          <span className="w-3 h-3 bg-green-600 rounded-full mr-2"></span>
          <span className="text-gray-600">Strong (Win Rate &gt;70%, Alpha &gt;10%)</span>
        </span>
        <span className="flex items-center">
          <span className="w-3 h-3 bg-yellow-600 rounded-full mr-2"></span>
          <span className="text-gray-600">Moderate (Win Rate 60-70%, Alpha 5-10%)</span>
        </span>
        <span className="flex items-center">
          <span className="w-3 h-3 bg-gray-600 rounded-full mr-2"></span>
          <span className="text-gray-600">Weak or No Data</span>
        </span>
      </div>
    </div>
  )
}

export default CompanyView
