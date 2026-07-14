'use client'

import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

interface ViewerProps {
  stlUrl: string | null
  // True while a generation request is in flight (no STL yet).
  generating: boolean
}

// Interactive three.js STL viewer: rotate / zoom / pan, auto-centered + framed,
// neutral material, basic lighting, resize-aware.
export default function Viewer({ stlUrl, generating }: ViewerProps) {
  const mountRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const controlsRef = useRef<OrbitControls | null>(null)
  const meshRef = useRef<THREE.Mesh | null>(null)

  const [loadingStl, setLoadingStl] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  // ---- one-time scene setup ------------------------------------------------
  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x0f172a) // slate-900
    sceneRef.current = scene

    const width = mount.clientWidth || 1
    const height = mount.clientHeight || 1

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 5000)
    camera.position.set(80, 80, 120)
    cameraRef.current = camera

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setSize(width, height)
    mount.appendChild(renderer.domElement)
    rendererRef.current = renderer

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = 0.1
    controlsRef.current = controls

    // lighting
    scene.add(new THREE.AmbientLight(0xffffff, 0.6))
    const key = new THREE.DirectionalLight(0xffffff, 0.9)
    key.position.set(1, 1, 1)
    scene.add(key)
    const fill = new THREE.DirectionalLight(0xffffff, 0.4)
    fill.position.set(-1, -0.5, -1)
    scene.add(fill)

    // subtle ground grid for spatial reference
    const grid = new THREE.GridHelper(400, 40, 0x334155, 0x1e293b)
    scene.add(grid)

    let frame = 0
    const animate = () => {
      frame = requestAnimationFrame(animate)
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    const onResize = () => {
      const w = mount.clientWidth || 1
      const h = mount.clientHeight || 1
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    const ro = new ResizeObserver(onResize)
    ro.observe(mount)
    window.addEventListener('resize', onResize)

    return () => {
      cancelAnimationFrame(frame)
      ro.disconnect()
      window.removeEventListener('resize', onResize)
      controls.dispose()
      renderer.dispose()
      if (renderer.domElement.parentNode === mount) {
        mount.removeChild(renderer.domElement)
      }
    }
  }, [])

  // ---- load STL whenever the url changes -----------------------------------
  useEffect(() => {
    if (!stlUrl) return
    const scene = sceneRef.current
    const camera = cameraRef.current
    const controls = controlsRef.current
    if (!scene || !camera || !controls) return

    let cancelled = false
    setLoadingStl(true)
    setLoadError(null)

    const loader = new STLLoader()
    loader.load(
      stlUrl,
      (geometry) => {
        if (cancelled) return

        // remove previous mesh
        if (meshRef.current) {
          scene.remove(meshRef.current)
          meshRef.current.geometry.dispose()
          ;(meshRef.current.material as THREE.Material).dispose()
          meshRef.current = null
        }

        geometry.computeVertexNormals()
        geometry.computeBoundingBox()
        const bbox = geometry.boundingBox!
        const center = new THREE.Vector3()
        bbox.getCenter(center)
        geometry.translate(-center.x, -center.y, -center.z)

        const material = new THREE.MeshStandardMaterial({
          color: 0x9ca3af,
          metalness: 0.25,
          roughness: 0.55,
          flatShading: false,
        })
        const mesh = new THREE.Mesh(geometry, material)
        scene.add(mesh)
        meshRef.current = mesh

        // frame the camera to the bounding sphere
        const size = new THREE.Vector3()
        bbox.getSize(size)
        const maxDim = Math.max(size.x, size.y, size.z) || 10
        const dist = maxDim * 2.2
        camera.position.set(dist, dist * 0.9, dist * 1.3)
        camera.near = maxDim / 100
        camera.far = maxDim * 100
        camera.updateProjectionMatrix()
        controls.target.set(0, 0, 0)
        controls.update()

        setLoadingStl(false)
      },
      undefined,
      (err) => {
        if (cancelled) return
        console.error('STL load error', err)
        setLoadError('Could not load the 3D model.')
        setLoadingStl(false)
      },
    )

    return () => {
      cancelled = true
    }
  }, [stlUrl])

  const showPlaceholder = !stlUrl && !generating

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl border border-slate-700 bg-slate-900">
      <div ref={mountRef} className="h-full w-full" data-testid="viewer-canvas" />

      {(loadingStl || generating) && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-900/70">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-600 border-t-sky-400" />
          <p className="text-sm text-slate-300">
            {generating ? 'Generating geometry…' : 'Loading model…'}
          </p>
        </div>
      )}

      {showPlaceholder && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center">
          <svg
            className="h-14 w-14 text-slate-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9"
            />
          </svg>
          <p className="text-sm font-medium text-slate-400">Your part will render here</p>
          <p className="text-xs text-slate-500">
            Describe a part and press Generate to see it in 3D.
          </p>
        </div>
      )}

      {loadError && (
        <div className="absolute inset-x-0 bottom-0 bg-red-950/80 px-4 py-2 text-center text-sm text-red-300">
          {loadError}
        </div>
      )}

      {stlUrl && !loadingStl && !loadError && (
        <div className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full bg-slate-800/80 px-3 py-1 text-xs text-slate-300">
          Drag to rotate · scroll to zoom · right-drag to pan
        </div>
      )}
    </div>
  )
}
