const app = document.querySelector('#app')

const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
}[char]))

const engineArt = (accent) => `
  <div class="engine-art" style="--accent:${accent}" aria-hidden="true">
    <div class="engine-cowl"><span>150</span></div>
    <div class="engine-neck"></div><div class="engine-leg"></div><div class="engine-prop">✦</div>
  </div>`

function modelCard(model) {
  return `<a class="model-card" href="/models/${model.slug}/">
    ${engineArt(model.accent)}
    <div class="model-card-copy">
      <span class="eyebrow">${escapeHtml(model.brand)} · ${model.horsepower} HP</span>
      <h3>${escapeHtml(model.model)}</h3>
      <p>${escapeHtml(model.family)}</p>
      <span class="view-link">View engine record <b>→</b></span>
    </div>
  </a>`
}

function renderHome(models) {
  const brands = [...new Set(models.map((model) => model.brand))]
  app.innerHTML = `
    <section class="hero">
      <div class="hero-copy">
        <span class="kicker">Marine engine knowledge base</span>
        <h1>Find the right information for your <em>outboard.</em></h1>
        <p>Structured model identities, generations, specifications and source-backed repair information — built for boat owners and marine technicians.</p>
        <a class="primary-button" href="#models">Explore test models <span>↓</span></a>
      </div>
      <div class="hero-scene" aria-hidden="true">
        <div class="sun"></div><div class="boat"><span></span></div>
        <div class="water water-one"></div><div class="water water-two"></div>
      </div>
    </section>

    <section class="trust-strip">
      <div><b>${models.length}</b><span>test models</span></div>
      <div><b>${brands.length}</b><span>outboard brands</span></div>
      <div><b>100%</b><span>separate from appliance data</span></div>
    </section>

    <section class="content-section" id="brands">
      <div class="section-heading"><div><span class="kicker">Browse the catalogue</span><h2>Outboard brands</h2></div><p>This first vertical slice validates the model and publication flow with clearly marked demonstration data.</p></div>
      <div class="brand-grid">
        ${brands.map((brand) => `<a class="brand-card" href="/brands/${brand.toLowerCase().replace(/[^a-z0-9]+/g, '-')}/"><span class="brand-monogram">${brand[0]}</span><div><h3>${escapeHtml(brand)}</h3><p>${models.filter((model) => model.brand === brand).length} test model</p></div><b>→</b></a>`).join('')}
      </div>
    </section>

    <section class="content-section models-section" id="models">
      <div class="section-heading"><div><span class="kicker">Engine records</span><h2>Featured outboard models</h2></div><span class="data-note">Synthetic test data</span></div>
      <div class="catalog-tools">
        <label class="search-box"><span>Search model or brand</span><input id="model-search" type="search" placeholder="Try F150 or Yamaha" autocomplete="off" /></label>
        <label><span>Brand</span><select id="brand-filter"><option value="">All brands</option>${brands.map((brand) => `<option value="${escapeHtml(brand)}">${escapeHtml(brand)}</option>`).join('')}</select></label>
        <label><span>Power</span><select id="power-filter"><option value="">All power ratings</option>${[...new Set(models.map((model) => model.horsepower))].map((hp) => `<option value="${hp}">${hp} HP</option>`).join('')}</select></label>
      </div>
      <p class="result-count" id="result-count"></p>
      <div class="model-grid" id="model-grid">${models.map(modelCard).join('')}</div>
      <div class="empty-results" id="empty-results" hidden><span>⌕</span><h3>No matching outboard models</h3><p>Try another model code, brand, or power rating.</p></div>
    </section>`

  const search = document.querySelector('#model-search')
  const brandFilter = document.querySelector('#brand-filter')
  const powerFilter = document.querySelector('#power-filter')
  const grid = document.querySelector('#model-grid')
  const empty = document.querySelector('#empty-results')
  const count = document.querySelector('#result-count')
  const applyFilters = () => {
    const query = search.value.trim().toLowerCase()
    const filtered = models.filter((model) =>
      (!query || `${model.brand} ${model.model} ${model.family}`.toLowerCase().includes(query))
      && (!brandFilter.value || model.brand === brandFilter.value)
      && (!powerFilter.value || String(model.horsepower) === powerFilter.value)
    )
    grid.innerHTML = filtered.map(modelCard).join('')
    empty.hidden = filtered.length > 0
    count.textContent = `${filtered.length} of ${models.length} models shown`
  }
  search.addEventListener('input', applyFilters)
  brandFilter.addEventListener('change', applyFilters)
  powerFilter.addEventListener('change', applyFilters)
  applyFilters()
}

function renderBrand(brand) {
  document.title = `${brand.name} outboards — OutboardRepairBase`
  app.innerHTML = `
    <section class="brand-hero">
      <a class="back-link" href="/">← All outboard brands</a>
      <span class="kicker">Outboard manufacturer</span>
      <h1>${escapeHtml(brand.name)}</h1>
      <p>Browse structured ${escapeHtml(brand.name)} outboard model records currently available in the test catalogue.</p>
    </section>
    <section class="content-section brand-models">
      <div class="section-heading"><div><span class="kicker">Published records</span><h2>${brand.models.length} test model${brand.models.length === 1 ? '' : 's'}</h2></div><span class="data-note">Synthetic test data</span></div>
      <div class="model-grid">${brand.models.map(modelCard).join('')}</div>
    </section>`
}

function renderModel(model) {
  document.title = `${model.name} — OutboardRepairBase`
  app.innerHTML = `
    <section class="model-hero">
      <div>
        <a class="back-link" href="/">← All outboard models</a>
        <span class="kicker">${escapeHtml(model.brand)} outboard</span>
        <h1>${escapeHtml(model.model)}</h1>
        <p>${escapeHtml(model.summary)}</p>
        <div class="tag-row"><span>${model.horsepower} HP</span><span>${escapeHtml(model.family)}</span><span>${escapeHtml(model.status)}</span></div>
      </div>
      ${engineArt(model.accent)}
    </section>
    <section class="model-content">
      <article>
        <span class="kicker">Verified structure · demonstration values</span>
        <h2>Technical overview</h2>
        <div class="identity-grid">
          <div><span>Technical generation</span><b>${escapeHtml(model.generation || 'Pending verification')}</b></div>
          <div><span>Model years</span><b>${model.modelYears?.length ? model.modelYears.join(' · ') : escapeHtml(model.years)}</b></div>
        </div>
        <h3 class="subheading">Specifications</h3>
        <div class="spec-table">${model.specifications.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`).join('')}</div>
      </article>
      <aside>
        <h3>Record status</h3>
        <div class="status-line"><i></i><span><b>Test record</b><small>Not published production content</small></span></div>
        <h3>Source notes</h3>
        ${model.sources.map((source) => `<p class="source-note">${escapeHtml(source)}</p>`).join('')}
        <p class="warning">Technical values shown here are prototype data and must not be used for servicing an engine.</p>
      </aside>
    </section>`
}

async function init() {
  try {
    const [models, health] = await Promise.all([
      fetch('/api/models').then((response) => {
        if (!response.ok) throw new Error('Catalogue request failed')
        return response.json()
      }),
      fetch('/api/health').then((response) => response.json()),
    ])
    document.querySelector('#data-source').textContent = health.dataSource === 'postgresql'
      ? 'PostgreSQL staging'
      : 'Local test fixture'
    const modelMatch = location.pathname.match(/^\/models\/([^/]+)\/?$/)
    if (modelMatch) {
      const model = models.find((item) => item.slug === modelMatch[1])
      if (!model) throw new Error('Model not found')
      return renderModel(model)
    }
    const brandMatch = location.pathname.match(/^\/brands\/([^/]+)\/?$/)
    if (brandMatch) {
      const response = await fetch(`/api/brands/${brandMatch[1]}`)
      if (!response.ok) throw new Error('Brand not found')
      return renderBrand(await response.json())
    }
    renderHome(models)
  } catch (error) {
    app.innerHTML = `<section class="error-state"><span>⚓</span><h1>Unable to load the catalogue</h1><p>${escapeHtml(error.message)}</p><a href="/">Return home</a></section>`
  }
}

init()
