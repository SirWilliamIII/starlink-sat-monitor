<template>
  <div class="globe-container">
    <div class="globe-header">
      <h2>🌍 SATELLITE CONSTELLATION</h2>
      <div class="globe-controls">
        <button @click="toggleRotation" class="control-btn">
          {{ autoRotate ? '⏸️ PAUSE' : '▶️ ROTATE' }}
        </button>
        <button @click="resetView" class="control-btn">
          🎯 RESET VIEW
        </button>
        <button @click="toggleSatellites" class="control-btn">
          {{ showSatellites ? '👁️ HIDE SATS' : '👁️ SHOW SATS' }}
        </button>
      </div>
    </div>
    
    <div class="globe-wrapper">
      <div ref="globeContainer" class="globe-canvas"></div>
      
      <!-- Satellite Info Panel -->
      <div v-if="selectedSatellite" class="satellite-info">
        <div class="info-header">
          <h3>{{ selectedSatellite.name }}</h3>
          <button @click="selectedSatellite = null" class="close-btn">✕</button>
        </div>
        <div class="info-content">
          <div class="info-row">
            <span class="label">NORAD ID:</span>
            <span class="value">{{ selectedSatellite.norad_id }}</span>
          </div>
          <div class="info-row">
            <span class="label">ALTITUDE:</span>
            <span class="value">{{ selectedSatellite.altitude_km?.toFixed(1) }} km</span>
          </div>
          <div class="info-row">
            <span class="label">VELOCITY:</span>
            <span class="value">{{ selectedSatellite.velocity_kmh?.toFixed(0) }} km/h</span>
          </div>
          <div class="info-row">
            <span class="label">POSITION:</span>
            <span class="value">{{ selectedSatellite.lat?.toFixed(2) }}°, {{ selectedSatellite.lng?.toFixed(2) }}°</span>
          </div>
        </div>
      </div>
      
      <!-- Globe Stats -->
      <div class="globe-stats">
        <div class="stat">
          <span class="stat-label">SATELLITES</span>
          <span class="stat-value">{{ satelliteCount }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">TRACKING</span>
          <span class="stat-value">{{ visibleSatellites }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">DATA AGE</span>
          <span class="stat-value">{{ dataAge }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'
import ThreeGlobe from 'three-globe'

export default {
  name: 'SatelliteGlobe',
  props: {
    satellites: {
      type: Object,
      default: () => ({})
    }
  },
  setup(props) {
    const globeContainer = ref(null)
    const selectedSatellite = ref(null)
    const autoRotate = ref(true)
    const showSatellites = ref(true)
    
    let scene, camera, renderer, globe, animationId, updateInterval
    const satelliteObjects = []
    const satellitePositionCache = new Map() // Cache for smooth interpolation
    
    // Reactive state
    const satelliteCount = ref(0)
    const visibleSatellites = ref(0)
    const dataAge = ref('--')
    
    const initGlobe = () => {
      if (!globeContainer.value) return
      
      // Set up scene
      scene = new THREE.Scene()
      scene.background = new THREE.Color(0x000000)
      
      // Set up camera
      camera = new THREE.PerspectiveCamera(
        75,
        globeContainer.value.clientWidth / globeContainer.value.clientHeight,
        0.1,
        10000
      )
      camera.position.set(0, 0, 300)
      
      // Set up renderer
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      renderer.setSize(globeContainer.value.clientWidth, globeContainer.value.clientHeight)
      renderer.setPixelRatio(window.devicePixelRatio)
      renderer.shadowMap.enabled = true
      renderer.shadowMap.type = THREE.PCFSoftShadowMap
      globeContainer.value.appendChild(renderer.domElement)
      
      // Create globe
      globe = new ThreeGlobe()
      globe.globeImageUrl('//unpkg.com/three-globe/example/img/earth-blue-marble.jpg')
      globe.bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
      
      // Style the globe
      globe.globeMaterial().bumpScale = 10
      globe.globeMaterial().shininess = 0.8
      globe.globeMaterial().transparent = true
      globe.globeMaterial().opacity = 0.9
      
      scene.add(globe)
      
      // Add ambient light
      const ambientLight = new THREE.AmbientLight(0x404040, 0.4)
      scene.add(ambientLight)
      
      // Add directional light (sun)
      const directionalLight = new THREE.DirectionalLight(0xffffff, 1.2)
      directionalLight.position.set(1, 1, 1)
      directionalLight.castShadow = true
      scene.add(directionalLight)
      
      // Add point light for electric blue glow
      const pointLight = new THREE.PointLight(0x00d4ff, 0.3, 1000)
      pointLight.position.set(0, 0, 500)
      scene.add(pointLight)
      
      // Add starfield
      addStarfield()
      
      // Set up mouse controls
      setupControls()
      
      // Start animation loop
      animate()
    }
    
    const addStarfield = () => {
      const starsGeometry = new THREE.BufferGeometry()
      const starCount = 2000
      const positions = new Float32Array(starCount * 3)
      
      for (let i = 0; i < starCount * 3; i += 3) {
        // Create stars in a sphere around the scene
        const radius = 2000 + Math.random() * 3000
        const theta = Math.random() * Math.PI * 2
        const phi = Math.acos(2 * Math.random() - 1)
        
        positions[i] = radius * Math.sin(phi) * Math.cos(theta)
        positions[i + 1] = radius * Math.sin(phi) * Math.sin(theta)
        positions[i + 2] = radius * Math.cos(phi)
      }
      
      starsGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
      
      const starsMaterial = new THREE.PointsMaterial({
        color: 0x00d4ff,
        size: 2,
        sizeAttenuation: false,
        transparent: true,
        opacity: 0.8
      })
      
      const stars = new THREE.Points(starsGeometry, starsMaterial)
      scene.add(stars)
    }
    
    const setupControls = () => {
      let isDragging = false
      let previousMousePosition = { x: 0, y: 0 }
      let rotationSpeed = { x: 0, y: 0 }
      
      const canvas = renderer.domElement
      const raycaster = new THREE.Raycaster()
      const mouse = new THREE.Vector2()
      
      // Mouse events for camera orbiting
      canvas.addEventListener('mousedown', (event) => {
        isDragging = true
        previousMousePosition = { x: event.clientX, y: event.clientY }
      })
      
      canvas.addEventListener('mousemove', (event) => {
        if (!isDragging) return
        
        const deltaMove = {
          x: event.clientX - previousMousePosition.x,
          y: event.clientY - previousMousePosition.y
        }
        
        // Get current camera position relative to Earth center
        const spherical = new THREE.Spherical()
        spherical.setFromVector3(camera.position)
        
        // Update spherical coordinates (orbit camera around Earth)
        spherical.theta -= deltaMove.x * 0.01  // Horizontal rotation
        spherical.phi += deltaMove.y * 0.01    // Vertical rotation
        
        // Clamp vertical rotation to avoid flipping
        spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi))
        
        // Update camera position
        camera.position.setFromSpherical(spherical)
        camera.lookAt(0, 0, 0)  // Always look at Earth center
        
        previousMousePosition = { x: event.clientX, y: event.clientY }
        
        // Disable auto-rotation when manually dragging
        autoRotate.value = false
      })
      
      canvas.addEventListener('mouseup', (event) => {
        isDragging = false
      })
      
      // Click detection for satellites
      canvas.addEventListener('click', (event) => {
        if (isDragging) return // Don't trigger click if we were dragging
        
        // Calculate mouse position in normalized device coordinates
        const rect = canvas.getBoundingClientRect()
        mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
        mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
        
        // Update raycaster
        raycaster.setFromCamera(mouse, camera)
        
        // Get satellite meshes only (not glow objects)
        const satelliteMeshes = satelliteObjects.filter((obj, index) => index % 2 === 0)
        const intersects = raycaster.intersectObjects(satelliteMeshes)
        
        if (intersects.length > 0) {
          const satellite = intersects[0].object.userData
          selectedSatellite.value = satellite
          console.log('🛰️ Clicked satellite:', satellite.name)
        } else {
          selectedSatellite.value = null
        }
      })
      
      // Mouse wheel for zoom
      canvas.addEventListener('wheel', (event) => {
        event.preventDefault()
        const zoomSpeed = 0.1
        const zoom = event.deltaY * zoomSpeed
        
        camera.position.multiplyScalar(1 + zoom * 0.01)
        
        // Clamp zoom
        const distance = camera.position.length()
        if (distance < 150) {
          camera.position.normalize().multiplyScalar(150)
        } else if (distance > 1000) {
          camera.position.normalize().multiplyScalar(1000)
        }
      })
      
      // Touch events for mobile
      let lastTouchDistance = 0
      
      canvas.addEventListener('touchstart', (event) => {
        if (event.touches.length === 1) {
          isDragging = true
          previousMousePosition = {
            x: event.touches[0].clientX,
            y: event.touches[0].clientY
          }
        } else if (event.touches.length === 2) {
          lastTouchDistance = Math.hypot(
            event.touches[0].clientX - event.touches[1].clientX,
            event.touches[0].clientY - event.touches[1].clientY
          )
        }
      })
      
      canvas.addEventListener('touchmove', (event) => {
        event.preventDefault()
        
        if (event.touches.length === 1 && isDragging) {
          const deltaMove = {
            x: event.touches[0].clientX - previousMousePosition.x,
            y: event.touches[0].clientY - previousMousePosition.y
          }
          
          // Update camera position instead of globe rotation
          const spherical = new THREE.Spherical()
          spherical.setFromVector3(camera.position)
          
          spherical.theta -= deltaMove.x * 0.01
          spherical.phi += deltaMove.y * 0.01
          spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, spherical.phi))
          
          camera.position.setFromSpherical(spherical)
          camera.lookAt(0, 0, 0)
          
          previousMousePosition = {
            x: event.touches[0].clientX,
            y: event.touches[0].clientY
          }
          
          autoRotate.value = false
        } else if (event.touches.length === 2) {
          const touchDistance = Math.hypot(
            event.touches[0].clientX - event.touches[1].clientX,
            event.touches[0].clientY - event.touches[1].clientY
          )
          
          const zoomFactor = touchDistance / lastTouchDistance
          camera.position.multiplyScalar(1 / zoomFactor)
          
          const distance = camera.position.length()
          if (distance < 150) {
            camera.position.normalize().multiplyScalar(150)
          } else if (distance > 1000) {
            camera.position.normalize().multiplyScalar(1000)
          }
          
          lastTouchDistance = touchDistance
        }
      })
      
      canvas.addEventListener('touchend', () => {
        isDragging = false
      })
    }
    
    const updateSatellites = () => {
      console.log('🌍 Globe updateSatellites called with:', props.satellites)
      
      if (!globe) {
        console.log('❌ Globe not initialized yet')
        return
      }
      
      if (!props.satellites?.positions) {
        console.log('❌ No satellite positions in props:', props.satellites)
        return
      }
      
      if (!showSatellites.value) {
        console.log('👁️ Satellites hidden by toggle')
        // Clear existing satellites
        satelliteObjects.forEach(obj => {
          scene.remove(obj)
        })
        satelliteObjects.length = 0
        return
      }
      
      const positions = props.satellites.positions || []
      console.log(`🛰️ Processing ${positions.length} satellite positions`)
      
      // If we don't have satellites yet, create them
      if (satelliteObjects.length === 0) {
        createSatelliteObjects(positions)
      } else {
        // Update existing satellite positions smoothly
        updateSatellitePositions(positions)
      }
      
      // Update stats
      satelliteCount.value = props.satellites.satellite_count || 0
      visibleSatellites.value = positions.length
      
      // Update data age
      if (props.satellites.timestamp) {
        const age = Date.now() - new Date(props.satellites.timestamp)
        const minutes = Math.floor(age / 60000)
        dataAge.value = minutes < 1 ? '<1m' : `${minutes}m`
      }
    }
    
    const createSatelliteObjects = (positions) => {
      positions.forEach((satellite, index) => {
        if (!satellite.lat || !satellite.lng) return
        
        // Create satellite marker
        const satelliteGeometry = new THREE.SphereGeometry(0.8, 8, 8)
        const satelliteMaterial = new THREE.MeshBasicMaterial({
          color: 0x00ff88,
          transparent: true,
          opacity: 0.9
        })
        
        const satelliteMesh = new THREE.Mesh(satelliteGeometry, satelliteMaterial)
        
        // Position satellite on globe surface
        const position = calculateSatellitePosition(satellite)
        satelliteMesh.position.copy(position)
        
        // Store satellite data
        satelliteMesh.userData = satellite
        satelliteMesh.noradId = satellite.norad_id
        
        // Add click handler
        satelliteMesh.callback = () => {
          selectedSatellite.value = satellite
        }
        
        // Add glowing effect
        const glowGeometry = new THREE.SphereGeometry(1.4, 8, 8)
        const glowMaterial = new THREE.MeshBasicMaterial({
          color: 0x00d4ff,
          transparent: true,
          opacity: 0.3
        })
        const glow = new THREE.Mesh(glowGeometry, glowMaterial)
        glow.position.copy(position)
        glow.noradId = satellite.norad_id
        
        scene.add(satelliteMesh)
        scene.add(glow)
        satelliteObjects.push(satelliteMesh, glow)
        
        // Cache current position for interpolation
        satellitePositionCache.set(satellite.norad_id, {
          current: position.clone(),
          target: position.clone(),
          velocity: new THREE.Vector3(),
          lastUpdate: Date.now()
        })
      })
    }
    
    const updateSatellitePositions = (positions) => {
      console.log('🔄 Updating satellite positions:', positions.length)
      
      // Create a map of new positions by NORAD ID
      const newPositions = new Map()
      positions.forEach(sat => {
        newPositions.set(sat.norad_id, sat)
      })
      
      let positionsUpdated = 0
      
      // Update existing satellites
      satelliteObjects.forEach((obj, index) => {
        if (!obj.noradId) return
        
        const newSat = newPositions.get(obj.noradId)
        if (!newSat) return
        
        const newPosition = calculateSatellitePosition(newSat)
        const cache = satellitePositionCache.get(obj.noradId)
        
        if (cache) {
          // Check if position actually changed
          const oldPos = cache.target.clone()
          const distance = oldPos.distanceTo(newPosition)
          
          if (distance > 0.1) { // Only update if significant movement
            console.log(`📍 Satellite ${newSat.name} moved ${distance.toFixed(2)} units`)
            positionsUpdated++
          }
          
          // Calculate velocity for smooth interpolation
          const timeDiff = (Date.now() - cache.lastUpdate) / 1000 // seconds
          if (timeDiff > 0) {
            cache.velocity.copy(newPosition).sub(cache.target).divideScalar(timeDiff)
          }
          
          cache.target.copy(newPosition)
          cache.lastUpdate = Date.now()
          
          // Update userData for click info
          obj.userData = newSat
        }
      })
      
      console.log(`📊 Updated ${positionsUpdated} satellite positions`)
    }
    
    const calculateSatellitePosition = (satellite) => {
      const phi = (90 - satellite.lat) * (Math.PI / 180)
      const theta = (satellite.lng + 180) * (Math.PI / 180)
      
      // Use actual altitude for more realistic positioning
      const earthRadius = 100
      const altitudeScale = 0.05 // Scale down altitude for visualization
      const radius = earthRadius + (satellite.altitude_km || 550) * altitudeScale
      
      return new THREE.Vector3(
        radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.cos(phi),
        radius * Math.sin(phi) * Math.sin(theta)
      )
    }
    
    const interpolateSatelliteMovement = () => {
      // Smooth interpolation between position updates
      const now = Date.now()
      
      satelliteObjects.forEach((obj, index) => {
        if (!obj.noradId) return
        
        const cache = satellitePositionCache.get(obj.noradId)
        if (!cache) return
        
        const timeSinceUpdate = (now - cache.lastUpdate) / 1000
        const lerpFactor = Math.min(timeSinceUpdate * 0.5, 1) // Smooth interpolation
        
        // Interpolate to target position
        cache.current.lerp(cache.target, lerpFactor * 0.1)
        obj.position.copy(cache.current)
      })
    }
    
    const animate = () => {
      animationId = requestAnimationFrame(animate)
      
      // Auto-rotate camera around Earth (instead of rotating Earth)
      if (autoRotate.value && globe) {
        const spherical = new THREE.Spherical()
        spherical.setFromVector3(camera.position)
        spherical.theta += 0.003  // Orbit camera around Earth
        camera.position.setFromSpherical(spherical)
        camera.lookAt(0, 0, 0)
      }
      
      // Interpolate satellite movement for smooth motion
      interpolateSatelliteMovement()
      
      // Animate satellite glow
      satelliteObjects.forEach((obj, index) => {
        if (index % 2 === 1) { // Glow objects
          obj.material.opacity = 0.2 + 0.1 * Math.sin(Date.now() * 0.003 + index)
        }
      })
      
      renderer.render(scene, camera)
    }
    
    const handleResize = () => {
      if (!globeContainer.value || !camera || !renderer) return
      
      const width = globeContainer.value.clientWidth
      const height = globeContainer.value.clientHeight
      
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    }
    
    // Control functions
    const toggleRotation = () => {
      autoRotate.value = !autoRotate.value
    }
    
    const resetView = () => {
      if (!globe || !camera) return
      
      // Reset camera to default orbital position
      camera.position.set(0, 0, 300)
      camera.lookAt(0, 0, 0)
      
      autoRotate.value = true
    }
    
    const toggleSatellites = () => {
      showSatellites.value = !showSatellites.value
      updateSatellites()
    }
    
    // Watch for satellite data changes
    watch(() => props.satellites, updateSatellites, { deep: true })
    
    onMounted(() => {
      initGlobe()
      window.addEventListener('resize', handleResize)
      
      // Start automatic satellite position updates every 30 seconds
      updateInterval = setInterval(() => {
        if (props.satellites?.positions) {
          console.log('🕒 Auto-updating satellite positions...')
          // Emit event to parent to fetch new data
          // This will trigger a prop update which will call updateSatellites
        }
      }, 30000) // 30 seconds
    })
    
    onUnmounted(() => {
      if (animationId) {
        cancelAnimationFrame(animationId)
      }
      if (updateInterval) {
        clearInterval(updateInterval)
      }
      window.removeEventListener('resize', handleResize)
      
      // Clean up Three.js objects
      if (renderer) {
        renderer.dispose()
      }
    })
    
    return {
      globeContainer,
      selectedSatellite,
      autoRotate,
      showSatellites,
      satelliteCount,
      visibleSatellites,
      dataAge,
      toggleRotation,
      resetView,
      toggleSatellites
    }
  }
}
</script>

<style scoped>
.globe-container {
  background: var(--glass-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: 20px;
  padding: var(--space-lg);
  box-shadow: var(--glass-shadow);
  position: relative;
  overflow: hidden;
}

.globe-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-lg);
  padding-bottom: var(--space-md);
  border-bottom: 1px solid rgba(0, 212, 255, 0.2);
}

.globe-header h2 {
  font-family: var(--font-display);
  font-size: 1.4rem;
  font-weight: 600;
  color: #ffffff;
  text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
  letter-spacing: 0.05em;
  margin: 0;
}

.globe-controls {
  display: flex;
  gap: var(--space-sm);
}

.control-btn {
  padding: var(--space-xs) var(--space-sm);
  background: var(--glass-bg);
  border: 1px solid var(--electric-cyan);
  border-radius: 15px;
  color: var(--electric-cyan);
  font-family: var(--font-display);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
  backdrop-filter: blur(10px);
}

.control-btn:hover {
  background: var(--electric-cyan);
  color: var(--space-black);
  box-shadow: 0 0 15px rgba(0, 212, 255, 0.5);
}

.globe-wrapper {
  position: relative;
  height: 500px;
  border-radius: 15px;
  overflow: hidden;
}

.globe-canvas {
  width: 100%;
  height: 100%;
  border-radius: 15px;
}

.satellite-info {
  position: absolute;
  top: var(--space-md);
  right: var(--space-md);
  background: rgba(26, 26, 46, 0.95);
  backdrop-filter: blur(20px);
  border: 1px solid var(--electric-cyan);
  border-radius: 15px;
  padding: var(--space-md);
  min-width: 250px;
  box-shadow: 0 0 20px rgba(0, 212, 255, 0.3);
}

.info-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-sm);
}

.info-header h3 {
  font-family: var(--font-display);
  font-size: 1.1rem;
  color: var(--electric-cyan);
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.7);
  font-size: 1.2rem;
  cursor: pointer;
  padding: 0;
  transition: color var(--transition-fast);
}

.close-btn:hover {
  color: var(--electric-cyan);
}

.info-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.label {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.7);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.value {
  font-family: var(--font-display);
  font-size: 0.9rem;
  color: #ffffff;
  font-weight: 500;
}

.globe-stats {
  position: absolute;
  bottom: var(--space-md);
  left: var(--space-md);
  display: flex;
  gap: var(--space-md);
}

.stat {
  background: rgba(26, 26, 46, 0.9);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(0, 212, 255, 0.3);
  border-radius: 10px;
  padding: var(--space-sm);
  text-align: center;
  min-width: 80px;
}

.stat-label {
  display: block;
  font-size: 0.7rem;
  color: rgba(255, 255, 255, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-xs);
}

.stat-value {
  display: block;
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--electric-cyan);
  text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
}

/* Responsive */
@media (max-width: 768px) {
  .globe-header {
    flex-direction: column;
    gap: var(--space-sm);
    text-align: center;
  }
  
  .globe-wrapper {
    height: 400px;
  }
  
  .satellite-info {
    position: static;
    margin-top: var(--space-md);
  }
  
  .globe-stats {
    position: static;
    justify-content: center;
    margin-top: var(--space-md);
  }
}
</style>