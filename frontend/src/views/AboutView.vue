<template>
  <div class="about-page">
    <div class="about-container">

      <!-- Header -->
      <div class="about-header">
        <h1>GeoFlowCraft</h1>
        <p class="subtitle">Multi-Agent GIS Web Platform for Intelligent Satellite Image Analysis</p>
      </div>

      <!-- Overview -->
      <section class="about-section">
        <h2>About the Platform</h2>
        <p>
          GeoFlowCraft is a web-based geospatial platform that integrates AI-powered satellite image processing 
          with GIS analysis capabilities. The platform combines Sentinel-2 optical imagery with Sentinel-1 SAR data 
          to deliver enhanced spatial products, change detection maps, and vegetation analysis — all through an 
          intuitive map-based interface.
        </p>
        <p>
          This platform was developed as part of a bachelor thesis at the University of Bucharest, Faculty of 
          Mathematics and Computer Science.
        </p>
      </section>

      <!-- Processing Models -->
      <section class="about-section">
        <h2>Available Processing Models</h2>

        <div class="model-cards">
          <div class="model-card">
            <div class="model-title">Super Resolution</div>
            <div class="model-badge sr">SAR-Optical Fusion</div>
            <p>
              Enhances Sentinel-2 imagery from 10m to 2.5m resolution by fusing optical (S2) and SAR (S1) data 
              using a dual-branch deep learning architecture. Three output modes are available: 
              <strong>Sharp</strong> (best visual quality), <strong>Balanced</strong> (visual + spectral), 
              and <strong>Fidelity</strong> (maximum spectral accuracy for quantitative analysis).
            </p>
          </div>

          <div class="model-card">
            <div class="model-title">Canopy Height</div>
            <div class="model-badge chm">Global CHM</div>
            <p>
              Estimates vegetation canopy height using the Global Canopy Height Model (ETH Zürich). 
              Requires Sentinel-2 Level-2A scenes. Produces height maps in meters with uncertainty estimates.
            </p>
          </div>

          <div class="model-card">
            <div class="model-title">Change Detection — Urban</div>
            <div class="model-badge cd-sr">CVA</div>
            <p>
              Detects urban and land-use changes between two time periods using Change Vector Analysis (CVA) 
              on super-resolved imagery. Outputs include magnitude maps, ΔNDVI, and binary change masks 
              with area statistics.
            </p>
          </div>

          <div class="model-card">
            <div class="model-title">Deforestation Detection</div>
            <div class="model-badge cd-chm">ΔCHM</div>
            <p>
              Monitors forest canopy changes by comparing two Canopy Height Model outputs from different 
              time periods. Identifies areas of canopy loss (deforestation) and regrowth with 
              quantified area estimates.
            </p>
          </div>
        </div>
      </section>

      <!-- How to Use -->
      <section class="about-section">
        <h2>How to Use</h2>

        <div class="steps">
          <div class="step">
            <div class="step-number">1</div>
            <div class="step-content">
              <strong>Choose a Processing Task</strong>
              <p>Click <em>Model Processing</em> in the top navigation bar. A dialog will appear with four task cards — select the one that matches your analysis goal.</p>
            </div>
          </div>

          <div class="step">
            <div class="step-number">2</div>
            <div class="step-content">
              <strong>Draw Your Area of Interest</strong>
              <p>Use the polygon drawing tool to outline the geographic area you want to analyze on the map. The platform will search for available satellite imagery covering your selection.</p>
            </div>
          </div>

          <div class="step">
            <div class="step-number">3</div>
            <div class="step-content">
              <strong>Select Time Period and Scene</strong>
              <p>Choose a date range to search for available Sentinel-2 scenes. For Change Detection, you will select two separate time periods (T1 and T2). The platform verifies SAR data availability before proceeding.</p>
            </div>
          </div>

          <div class="step">
            <div class="step-number">4</div>
            <div class="step-content">
              <strong>Name and Process</strong>
              <p>Give your result a descriptive name and start processing. A progress dialog will keep you informed about each pipeline stage. Results are automatically published to the map.</p>
            </div>
          </div>

          <div class="step">
            <div class="step-number">5</div>
            <div class="step-content">
              <strong>View and Download Results</strong>
              <p>Processed results appear as layers on the map. Use <em>View Results</em> to browse all outputs and download GeoTIFF files or ZIP archives for further analysis.</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Change Detection Modes -->
      <section class="about-section">
        <h2>Change Detection — Data Source Options</h2>
        <p>When selecting a Change Detection task, you have three options for providing input data:</p>
        <div class="options-list">
          <div class="option-item">
            <strong>New Scenes</strong> — Draw an area, select two date ranges (T1 and T2), and choose one satellite scene from each period. The platform downloads and processes both from scratch.
          </div>
          <div class="option-item">
            <strong>From Existing Results</strong> — Select two previously processed SR or CHM results directly from your processing history. No download or area selection needed.
          </div>
          <div class="option-item">
            <strong>Mix</strong> — Combine one existing result with one newly downloaded scene. Useful when you already have a baseline and want to compare it with recent imagery.
          </div>
        </div>
      </section>

      <!-- Important Notice -->
      <section class="about-section warning-section">
        <h2>Important Notes on Map Visualization</h2>
        <div class="warning-box">
          <div class="warning-icon">⚠</div>
          <div class="warning-content">
            <strong>Super Resolution layers on the map use an RGB conversion</strong> for display purposes. 
            During this conversion, a percentile-based stretch (2nd–98th percentile per band) is applied to 
            map the original float32 reflectance values to 8-bit RGB. This means the colors you see on the 
            map may not exactly represent the original spectral values.
            <br><br>
            <strong>For accurate spectral analysis</strong>, always download the original GeoTIFF files from 
            the <em>View Results</em> panel and open them in dedicated geospatial software such as 
            <strong>QGIS</strong>, <strong>SNAP</strong>, or <strong>ArcGIS</strong>. The downloaded files 
            contain the full float32 reflectance data with proper georeferencing.
          </div>
        </div>
        <div class="info-box">
          <div class="info-icon">ℹ</div>
          <div class="info-content">
            <strong>Canopy Height</strong> layers are visualized using a viridis color ramp (0–40m range) 
            which accurately represents the height values. These can be used directly for visual inspection 
            on the map.
          </div>
        </div>
      </section>

      <!-- Footer -->
      <div class="about-footer">
      </div>

    </div>
  </div>
</template>

<script>
export default {
  name: "AboutView",
  components: {},
  computed: {},
  methods: {}
}
</script>

<style lang="scss" scoped>
.about-page {
  min-height: 100vh;
  background: #0f172a;
  color: #e2e8f0;
  overflow-y: auto;
  padding: 2rem;
}

.about-container {
  max-width: 900px;
  margin: 0 auto;
}

.about-header {
  text-align: center;
  margin-bottom: 3rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid rgba(20, 184, 166, 0.3);

  h1 {
    font-size: 2.5rem;
    font-weight: 700;
    color: rgb(20, 184, 166);
    margin-bottom: 0.5rem;
  }

  .subtitle {
    font-size: 1.1rem;
    color: #94a3b8;
  }
}

.about-section {
  margin-bottom: 2.5rem;

  h2 {
    font-size: 1.4rem;
    font-weight: 600;
    color: #f1f5f9;
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  p {
    color: #cbd5e1;
    line-height: 1.7;
    margin-bottom: 0.75rem;
  }
}

.model-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

.model-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 1.25rem;

  .model-title {
    font-weight: 600;
    font-size: 1.05rem;
    color: #f1f5f9;
    margin-bottom: 0.5rem;
  }

  .model-badge {
    display: inline-block;
    font-size: 0.7rem;
    padding: 0.2rem 0.6rem;
    border-radius: 12px;
    margin-bottom: 0.75rem;
    font-weight: 500;

    &.sr { background: rgba(20, 184, 166, 0.2); color: #5eead4; }
    &.chm { background: rgba(132, 204, 22, 0.2); color: #bef264; }
    &.cd-sr { background: rgba(239, 68, 68, 0.2); color: #fca5a5; }
    &.cd-chm { background: rgba(34, 197, 94, 0.2); color: #86efac; }
  }

  p {
    font-size: 0.875rem;
    color: #94a3b8;
    line-height: 1.6;
  }
}

.steps {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.step {
  display: flex;
  gap: 1rem;
  align-items: flex-start;

  .step-number {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(20, 184, 166, 0.2);
    color: rgb(20, 184, 166);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.9rem;
  }

  .step-content {
    strong {
      display: block;
      color: #f1f5f9;
      margin-bottom: 0.25rem;
    }

    p {
      font-size: 0.9rem;
      color: #94a3b8;
      margin: 0;
    }
  }
}

.options-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;

  .option-item {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-size: 0.9rem;
    color: #94a3b8;
    line-height: 1.6;

    strong {
      color: #e2e8f0;
    }
  }
}

.warning-section {
  .warning-box, .info-box {
    display: flex;
    gap: 1rem;
    padding: 1.25rem;
    border-radius: 10px;
    margin-bottom: 1rem;
    line-height: 1.7;
    font-size: 0.9rem;
  }

  .warning-box {
    background: rgba(234, 179, 8, 0.08);
    border: 1px solid rgba(234, 179, 8, 0.25);
    color: #fde68a;

    .warning-icon {
      font-size: 1.5rem;
      flex-shrink: 0;
    }

    strong {
      color: #fef08a;
    }
  }

  .info-box {
    background: rgba(59, 130, 246, 0.08);
    border: 1px solid rgba(59, 130, 246, 0.25);
    color: #93c5fd;

    .info-icon {
      font-size: 1.5rem;
      flex-shrink: 0;
    }

    strong {
      color: #bfdbfe;
    }
  }
}

.tech-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.tech-item {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 0.75rem 1rem;

  .tech-label {
    font-size: 0.75rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.25rem;
  }

  .tech-value {
    font-size: 0.9rem;
    color: #e2e8f0;
  }
}

.about-footer {
  text-align: center;
  margin-top: 3rem;
  padding-top: 2rem;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  color: #64748b;
  font-size: 0.85rem;

  .author {
    color: rgb(20, 184, 166);
    margin-top: 0.25rem;
  }
}

@media (max-width: 768px) {
  .model-cards, .tech-grid {
    grid-template-columns: 1fr;
  }
}
</style>