<template>
  <div id="app">
    <!-- Space Loading Screen -->
    <div v-if="initialLoading" class="loading-screen">
      <div class="loading-content">
        <div class="loading-logo">
          <div class="satellite-icon">🛰️</div>
          <div class="orbit-ring orbit-1"></div>
          <div class="orbit-ring orbit-2"></div>
          <div class="orbit-ring orbit-3"></div>
        </div>
        <h1 class="loading-title">STARLINK COMMAND CENTER</h1>
        <div class="loading-status">
          <div class="loading-bar">
            <div class="loading-fill"></div>
          </div>
          <p class="loading-text">{{ loadingText }}</p>
        </div>
      </div>
    </div>

    <!-- Mission Control Header -->
    <header class="header">
      <div class="header-content">
        <h1 class="title">
          🛰️ STARLINK COMMAND CENTER
        </h1>
        <div class="connection-status" :class="{ connected: serverConnected }">
          <div class="status-dot"></div>
          <span>{{ serverConnected ? 'SYSTEM ONLINE' : 'OFFLINE' }}</span>
        </div>
      </div>
    </header>

    <!-- Main Dashboard Grid -->
    <main class="dashboard">
      
      <!-- 3D Satellite Globe -->
      <div class="globe-section">
        <SatelliteGlobe :satellites="satelliteData" />
      </div>
      
      <!-- Status Cards Grid -->
      <div class="status-grid">
        
        <!-- Starlink Telemetry Card -->
        <div class="status-card starlink-card">
          <div class="card-header">
            <h2>📡 STARLINK TELEMETRY</h2>
            <div class="quality-badge" :class="getQualityClass(starlinkData.connection_quality)">
              {{ starlinkData.connection_quality || 'UNKNOWN' }}
            </div>
          </div>
          
          <div class="card-content">
            <div v-if="starlinkData.connected" class="metrics-grid">
              <div class="metric">
                <span class="metric-label">PING</span>
                <span class="metric-value">{{ starlinkData.ping_latency_ms || 0 }}ms</span>
              </div>
              <div class="metric">
                <span class="metric-label">DOWNLOAD</span>
                <span class="metric-value success-text">
                  {{ typeof starlinkData.download_mbps === 'number' ? starlinkData.download_mbps + ' Mbps' : (starlinkData.download_mbps || 'N/A') }}
                </span>
              </div>
              <div class="metric">
                <span class="metric-label">UPLOAD</span>
                <span class="metric-value success-text">
                  {{ typeof starlinkData.upload_mbps === 'number' ? starlinkData.upload_mbps + ' Mbps' : (starlinkData.upload_mbps || 'N/A') }}
                </span>
              </div>
              <div class="metric">
                <span class="metric-label">SIGNAL</span>
                <span class="metric-value">{{ Math.round((starlinkData.signal_quality || 0) * 100) }}%</span>
              </div>
              <div class="metric">
                <span class="metric-label">UPTIME</span>
                <span class="metric-value">{{ starlinkData.uptime_hours || 'N/A' }}</span>
              </div>
              <div class="metric">
                <span class="metric-label">OBSTRUCTED</span>
                <span class="metric-value" :class="{ 'error-text': starlinkData.obstruction_detected }">
                  {{ starlinkData.obstruction_detected ? 'YES' : 'NO' }}
                </span>
              </div>
            </div>
            
            <div v-else class="error-state">
              <div class="error-icon">⚠️</div>
              <div class="error-message">
                <strong>DISH UNREACHABLE</strong>
                <p>{{ starlinkData.error || 'Unable to establish connection with Starlink terminal' }}</p>
                <small>Verify network connection to Starlink system</small>
              </div>
            </div>
          </div>
        </div>

        <!-- System Monitor Card -->
        <div class="status-card network-card">
          <div class="card-header">
            <h2>🖥️ SYSTEM MONITOR</h2>
          </div>
          
          <div class="card-content">
            <div class="metrics-grid">
              <div class="metric">
                <span class="metric-label">SERVER</span>
                <span class="metric-value" :class="{ 'success-text': serverConnected, 'error-text': !serverConnected }">
                  {{ serverConnected ? 'ONLINE' : 'OFFLINE' }}
                </span>
              </div>
              <div class="metric">
                <span class="metric-label">MONITORING</span>
                <span class="metric-value success-text">
                  ACTIVE
                </span>
              </div>
              <div class="metric">
                <span class="metric-label">LAST UPDATE</span>
                <span class="metric-value">{{ formatTimestamp(lastUpdate) }}</span>
              </div>
              <div class="metric">
                <span class="metric-label">UPDATE RATE</span>
                <span class="metric-value">10 SEC</span>
              </div>
              <div class="metric">
                <span class="metric-label">DATA POINTS</span>
                <span class="metric-value success-text">{{ dataPointsCount }}</span>
              </div>
              <div class="metric">
                <span class="metric-label">SATELLITES</span>
                <span class="metric-value success-text">{{ satelliteCount }}</span>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- Mission Control Actions -->
      <div class="actions">
        <button @click="refreshAllData" :disabled="loading" class="btn btn-primary">
          <span>{{ loading ? '🔄 SCANNING...' : '🔄 REFRESH ALL' }}</span>
        </button>
        
        <button @click="exportMissionData" :disabled="!hasData" class="btn btn-secondary">
          <span>💾 EXPORT LOGS</span>
        </button>
      </div>

      <!-- System Status Messages -->
      <div v-if="statusMessages.length > 0" class="status-messages">
        <div class="card-header">
          <h2>📊 SYSTEM STATUS</h2>
        </div>
        <div class="status-message-grid">
          <div 
            v-for="(message, index) in statusMessages" 
            :key="index"
            class="status-message"
            :class="getMessageClass(message)"
          >
            {{ message }}
          </div>
        </div>
      </div>

      <!-- Technical Data Console -->
      <details class="raw-data">
        <summary>🔧 TECHNICAL DATA CONSOLE</summary>
        <pre>{{ JSON.stringify({ 
          starlink: starlinkData, 
          system: { 
            connected: serverConnected, 
            monitoring: monitoringActive,
            lastUpdate: lastUpdate,
            satellites: satelliteCount
          }
        }, null, 2) }}</pre>
      </details>

    </main>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { io } from 'socket.io-client'
import axios from 'axios'
import SatelliteGlobe from './components/SatelliteGlobe.vue'

export default {
  name: 'StarlinkCommandCenter',
  components: {
    SatelliteGlobe
  },
  setup() {
    // Reactive state
    const starlinkData = ref({})
    const satelliteData = ref({})
    const serverConnected = ref(false)
    const monitoringActive = ref(false)
    const lastUpdate = ref(null)
    const loading = ref(false)
    const socket = ref(null)
    const statusMessages = ref([])
    const initialLoading = ref(true)
    const loadingText = ref('Initializing systems...')

    // API configuration
    const API_BASE = 'http://localhost:5511'

    // Computed properties
    const hasData = computed(() => Object.keys(starlinkData.value).length > 0)
    
    const dataPointsCount = computed(() => {
      return hasData.value ? Object.keys(starlinkData.value).length : 0
    })

    const satelliteCount = computed(() => {
      return satelliteData.value?.satellite_count || 0
    })

    // WebSocket connection management
    const initSocket = () => {
      socket.value = io(API_BASE, {
        transports: ['websocket', 'polling']
      })
      
      socket.value.on('connect', () => {
        console.log('🚀 Connected to Starlink Command Center')
        serverConnected.value = true
        addStatusMessage('✅ Command Center connection established')
      })
      
      socket.value.on('disconnect', () => {
        console.log('❌ Disconnected from Command Center')
        serverConnected.value = false
        addStatusMessage('❌ Command Center connection lost')
      })
      
      socket.value.on('data_update', (data) => {
        console.log('📊 Receiving telemetry data:', data)
        
        if (data.starlink) {
          starlinkData.value = data.starlink
        }
        
        if (data.satellites) {
          satelliteData.value = data.satellites
        }
        
        monitoringActive.value = data.monitoring_active || false
        lastUpdate.value = new Date()
        
        // Add status messages based on data quality
        if (data.starlink?.connected) {
          const quality = data.starlink.connection_quality
          if (quality === 'Excellent') {
            addStatusMessage('🛰️ Starlink signal optimal')
          } else if (quality === 'Poor' || quality === 'Very Poor') {
            addStatusMessage('⚠️ Starlink signal degraded')
          }
        }
      })
      
      socket.value.on('error', (error) => {
        console.error('❌ Socket error:', error)
        addStatusMessage('❌ Communication error detected')
      })
    }

    // Status message management
    const addStatusMessage = (message) => {
      statusMessages.value.unshift(message)
      if (statusMessages.value.length > 10) {
        statusMessages.value.pop()
      }
    }

    const getMessageClass = (message) => {
      if (message.includes('✅')) return 'success'
      if (message.includes('⚠️')) return 'warning'
      if (message.includes('❌')) return 'error'
      return 'info'
    }

    // API interaction functions
    const refreshData = async () => {
      loading.value = true
      addStatusMessage('🔄 Initiating data refresh...')
      
      try {
        const response = await axios.get(`${API_BASE}/api/status`)
        starlinkData.value = response.data.starlink || {}
        monitoringActive.value = response.data.monitoring_active || false
        lastUpdate.value = new Date()
        
        addStatusMessage('✅ Data refresh completed')
        console.log('✅ Manual data refresh successful')
      } catch (error) {
        console.error('❌ Data refresh failed:', error)
        addStatusMessage('❌ Data refresh failed - check connection')
      } finally {
        loading.value = false
      }
    }

    const refreshAllData = async () => {
      loading.value = true
      addStatusMessage('🔄 Refreshing all systems...')
      
      try {
        // Refresh Starlink data
        await refreshData()
        
        // Refresh satellite data
        await fetchSatelliteData()
        
        addStatusMessage('✅ All systems refreshed')
      } catch (error) {
        addStatusMessage('❌ System refresh failed')
      } finally {
        loading.value = false
      }
    }


    const exportMissionData = () => {
      const missionData = {
        timestamp: new Date().toISOString(),
        mission_id: `STARLINK_${Date.now()}`,
        starlink_telemetry: starlinkData.value,
        satellite_data: satelliteData.value,
        system_status: {
          monitoring_active: monitoringActive.value,
          server_connected: serverConnected.value,
          last_update: lastUpdate.value
        },
        status_log: statusMessages.value
      }
      
      const blob = new Blob([JSON.stringify(missionData, null, 2)], { 
        type: 'application/json' 
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `starlink-mission-${new Date().toISOString().slice(0, 19)}.json`
      a.click()
      URL.revokeObjectURL(url)
      
      addStatusMessage('💾 Mission data exported successfully')
    }

    const fetchSatelliteData = async () => {
      try {
        console.log('🛰️ Fetching satellite data from:', `${API_BASE}/api/satellites`)
        addStatusMessage('🔄 Fetching satellite constellation...')
        
        const response = await axios.get(`${API_BASE}/api/satellites`)
        
        console.log('📡 Raw satellite response:', response.data)
        
        if (response.data) {
          satelliteData.value = response.data
          const count = response.data.satellite_count || 0
          const positions = response.data.positions_calculated || 0
          addStatusMessage(`🛰️ Loaded ${count} satellites (${positions} positioned)`)
          console.log('✅ Satellite data updated:', {
            count,
            positions,
            dataSource: response.data.data_source,
            timestamp: response.data.timestamp,
            firstSat: response.data.positions?.[0]
          })
          console.log('📊 Full satellite data:', response.data)
        } else {
          addStatusMessage('❌ No satellite data received')
        }
      } catch (error) {
        console.error('❌ Failed to fetch satellite data:', error)
        addStatusMessage(`❌ Satellite fetch failed: ${error.message}`)
      }
    }


    // Utility functions
    const getQualityClass = (quality) => {
      const qualityMap = {
        'excellent': 'excellent',
        'good': 'good',
        'fair': 'fair',
        'poor': 'poor',
        'very poor': 'very-poor'
      }
      return qualityMap[quality?.toLowerCase()] || 'unknown'
    }

    const formatTimestamp = (timestamp) => {
      if (!timestamp) return 'NEVER'
      return timestamp.toLocaleTimeString('en-US', { 
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      })
    }

    // Lifecycle management
    onMounted(() => {
      console.log('🚀 Initializing Starlink Command Center...')
      
      // Loading sequence
      const loadingSequence = [
        { text: 'Establishing satellite uplink...', delay: 800 },
        { text: 'Calibrating telemetry systems...', delay: 600 },
        { text: 'Loading satellite constellation...', delay: 1000 },
        { text: 'System ready', delay: 400 }
      ]
      
      let totalDelay = 0
      loadingSequence.forEach((step, index) => {
        totalDelay += step.delay
        setTimeout(() => {
          loadingText.value = step.text
          if (index === loadingSequence.length - 1) {
            setTimeout(() => {
              initialLoading.value = false
              initSocket()
              refreshData()
              fetchSatelliteData() // Fetch satellite data on startup
              addStatusMessage('🚀 Starlink Command Center initialized')
              
              // Start auto-refresh for real-time satellite movement
              setInterval(() => {
                fetchSatelliteData()
              }, 10000) // Update every 10 seconds
            }, 400)
          }
        }, totalDelay)
      })
    })

    onUnmounted(() => {
      if (socket.value) {
        socket.value.disconnect()
      }
    })

    return {
      // Data
      starlinkData,
      satelliteData,
      serverConnected,
      monitoringActive,
      lastUpdate,
      loading,
      statusMessages,
      initialLoading,
      loadingText,
      
      // Computed
      hasData,
      dataPointsCount,
      satelliteCount,
      
      // Methods
      refreshData,
      refreshAllData,
      exportMissionData,
      fetchSatelliteData,
      getQualityClass,
      formatTimestamp,
      getMessageClass
    }
  }
}
</script>

<style>
/* Status Messages */
.status-messages {
  margin-bottom: var(--space-2xl);
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: 15px;
  padding: var(--space-lg);
}

.status-message-grid {
  display: grid;
  gap: var(--space-sm);
  margin-top: var(--space-md);
}

.status-message {
  padding: var(--space-sm) var(--space-md);
  border-radius: 8px;
  font-family: var(--font-display);
  font-size: 0.9rem;
  letter-spacing: 0.02em;
  border-left: 3px solid;
  animation: slideInFromLeft 0.3s ease-out;
}

.status-message.success {
  background: rgba(0, 255, 136, 0.1);
  border-color: var(--success-glow);
  color: var(--success-glow);
}

.status-message.warning {
  background: rgba(255, 170, 0, 0.1);
  border-color: var(--warning-glow);
  color: var(--warning-glow);
}

.status-message.error {
  background: rgba(255, 51, 102, 0.1);
  border-color: var(--error-glow);
  color: var(--error-glow);
}

.status-message.info {
  background: rgba(102, 170, 255, 0.1);
  border-color: var(--info-glow);
  color: var(--info-glow);
}

/* Enhanced loading states */
.loading-indicator {
  position: relative;
  overflow: hidden;
}

.loading-indicator::after {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(0, 212, 255, 0.3), transparent);
  animation: dataStream 2s infinite;
}


/* Enhanced hover effects */
.btn:hover:not(:disabled) {
  transform: translateY(-3px) scale(1.02);
}

.metric:hover .metric-value {
  text-shadow: 0 0 15px currentColor;
}
</style>
