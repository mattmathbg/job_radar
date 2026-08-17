document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const kpiTotal = document.getElementById('kpi-total');
    const kpiRelevant = document.getElementById('kpi-relevant');
    const kpiBsScore = document.getElementById('kpi-bs-score');
    
    const filterSearch = document.getElementById('filter-search');
    const filterLocation = document.getElementById('filter-location');
    const filterBs = document.getElementById('filter-bs');
    const filterRelevant = document.getElementById('filter-relevant');
    const btnRefresh = document.getElementById('btn-refresh');

    const tabJobs = document.getElementById('tab-jobs');
    const tabTrends = document.getElementById('tab-trends');
    const viewJobs = document.getElementById('view-jobs');
    const viewTrends = document.getElementById('view-trends');
    
    const jobsGrid = document.getElementById('jobs-grid');
    const emptyState = document.getElementById('empty-state');
    const jobsCountBadge = document.getElementById('jobs-count-badge');
    const lastUpdateTime = document.getElementById('last-update-time');

    let debounceTimer;
    let chartTopTechInstance = null;
    let chartLocationInstance = null;
    let chartBsTechInstance = null;

    // Load initial stats, jobs and trends
    fetchStats();
    fetchJobs();

    // Tab Navigation
    tabJobs.addEventListener('click', () => {
        tabJobs.classList.add('active');
        tabTrends.classList.remove('active');
        viewJobs.classList.add('active');
        viewJobs.classList.remove('hidden');
        viewTrends.classList.remove('active');
        viewTrends.classList.add('hidden');
    });

    tabTrends.addEventListener('click', () => {
        tabTrends.classList.add('active');
        tabJobs.classList.remove('active');
        viewTrends.classList.add('active');
        viewTrends.classList.remove('hidden');
        viewJobs.classList.remove('active');
        viewJobs.classList.add('hidden');
        fetchTrends();
    });

    // Event listeners for filters
    filterSearch.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(fetchJobs, 300);
    });

    filterLocation.addEventListener('change', fetchJobs);
    filterBs.addEventListener('change', fetchJobs);
    filterRelevant.addEventListener('change', fetchJobs);
    
    btnRefresh.addEventListener('click', () => {
        const refreshIcon = btnRefresh.querySelector('.refresh-icon');
        refreshIcon.style.transform = 'rotate(360deg)';
        refreshIcon.style.transition = 'transform 0.5s ease';
        fetchStats();
        fetchJobs();
        if (viewTrends.classList.contains('active')) {
            fetchTrends();
        }
        setTimeout(() => {
            refreshIcon.style.transform = 'none';
            refreshIcon.style.transition = 'none';
        }, 500);
    });

    async function fetchStats() {
        try {
            const res = await fetch('/api/stats');
            if (res.ok) {
                const data = await res.json();
                kpiTotal.textContent = data.total_jobs || 0;
                kpiRelevant.textContent = data.relevant_jobs || 0;
                kpiBsScore.textContent = (data.avg_bullshit_score || 0).toFixed(1);
            }
        } catch (err) {
            console.error('Error fetching stats:', err);
        }
    }

    async function fetchJobs() {
        const search = filterSearch.value.trim();
        const location = filterLocation.value;
        const maxBs = filterBs.value;
        const relevantOnly = filterRelevant.checked;

        let queryParams = new URLSearchParams();
        if (search) queryParams.append('search', search);
        if (location && location !== 'all') queryParams.append('location', location);
        if (maxBs) queryParams.append('max_bullshit', maxBs);
        if (relevantOnly) queryParams.append('relevant_only', 'true');

        try {
            const res = await fetch(`/api/jobs?${queryParams.toString()}`);
            if (res.ok) {
                const data = await res.json();
                renderJobs(data.jobs || []);
                jobsCountBadge.textContent = data.count || 0;
                lastUpdateTime.textContent = `Mis à jour à ${new Date().toLocaleTimeString()}`;
            }
        } catch (err) {
            console.error('Error fetching jobs:', err);
            jobsGrid.innerHTML = `<div class="empty-state">❌ Erreur lors du chargement des offres.</div>`;
        }
    }

    async function fetchTrends() {
        try {
            const res = await fetch('/api/trends');
            if (res.ok) {
                const data = await res.json();
                renderTrendsCharts(data);
            }
        } catch (err) {
            console.error('Error fetching trends:', err);
        }
    }

    function renderTrendsCharts(data) {
        if (typeof Chart === 'undefined') return;

        // Chart 1: Top Technologies (Bar Chart)
        const topTech = data.top_technologies || [];
        const techLabels = topTech.map(t => t.name);
        const techCounts = topTech.map(t => t.count);

        const ctxTech = document.getElementById('chart-top-tech').getContext('2d');
        if (chartTopTechInstance) chartTopTechInstance.destroy();

        chartTopTechInstance = new Chart(ctxTech, {
            type: 'bar',
            data: {
                labels: techLabels.length ? techLabels : ['Aucune donnée'],
                datasets: [{
                    label: "Nombre d'offres",
                    data: techCounts.length ? techCounts : [0],
                    backgroundColor: 'rgba(139, 92, 246, 0.7)',
                    borderColor: '#8b5cf6',
                    borderWidth: 1.5,
                    borderRadius: 6,
                    hoverBackgroundColor: 'rgba(139, 92, 246, 0.95)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { ticks: { color: '#9ca3af', font: { family: 'Inter' } }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { ticks: { color: '#9ca3af', font: { family: 'Inter' } }, grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true }
                }
            }
        });

        // Chart 2: Location Distribution (Doughnut Chart)
        const locDist = data.location_distribution || {};
        const locLabels = Object.keys(locDist);
        const locCounts = Object.values(locDist);

        const ctxLoc = document.getElementById('chart-location').getContext('2d');
        if (chartLocationInstance) chartLocationInstance.destroy();

        chartLocationInstance = new Chart(ctxLoc, {
            type: 'doughnut',
            data: {
                labels: locLabels.length ? locLabels : ['Aucune donnée'],
                datasets: [{
                    data: locCounts.length ? locCounts : [1],
                    backgroundColor: [
                        'rgba(6, 182, 212, 0.8)',
                        'rgba(139, 92, 246, 0.8)',
                        'rgba(236, 72, 153, 0.8)',
                        'rgba(16, 185, 129, 0.8)'
                    ],
                    borderColor: '#090d16',
                    borderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#f3f4f6', font: { family: 'Inter', size: 12 } }
                    }
                }
            }
        });

        // Chart 3: Bullshit Score by Tech (Bar Chart)
        const bsPerTech = data.avg_bs_per_tech || {};
        const bsLabels = Object.keys(bsPerTech);
        const bsValues = Object.values(bsPerTech);

        const ctxBs = document.getElementById('chart-bs-tech').getContext('2d');
        if (chartBsTechInstance) chartBsTechInstance.destroy();

        chartBsTechInstance = new Chart(ctxBs, {
            type: 'bar',
            data: {
                labels: bsLabels.length ? bsLabels : ['Aucune donnée'],
                datasets: [{
                    label: "Score Bullshit Moyen (1-10)",
                    data: bsValues.length ? bsValues : [0],
                    backgroundColor: bsValues.map(v => v >= 7 ? 'rgba(239, 68, 68, 0.7)' : v >= 4 ? 'rgba(245, 158, 11, 0.7)' : 'rgba(16, 185, 129, 0.7)'),
                    borderColor: 'rgba(255,255,255,0.2)',
                    borderWidth: 1,
                    borderRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { ticks: { color: '#9ca3af', font: { family: 'Inter' } }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { ticks: { color: '#9ca3af', font: { family: 'Inter' } }, grid: { color: 'rgba(255,255,255,0.05)' }, min: 0, max: 10 }
                }
            }
        });
    }

    function renderJobs(jobs) {
        if (!jobs || jobs.length === 0) {
            jobsGrid.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');
        jobsGrid.innerHTML = jobs.map(job => createJobCardHTML(job)).join('');
    }

    function createJobCardHTML(job) {
        const bsScore = job.bullshit_score || 0;
        let bsClass = 'bs-low';
        let bsLabel = `Bullshit: ${bsScore}/10 🟢`;
        
        if (bsScore >= 7) {
            bsClass = 'bs-high';
            bsLabel = `Bullshit: ${bsScore}/10 🔴`;
        } else if (bsScore >= 4) {
            bsClass = 'bs-medium';
            bsLabel = `Bullshit: ${bsScore}/10 🟡`;
        }

        const techTags = (job.tech_stack || []).map(t => `<span class="tech-tag">${escapeHTML(t)}</span>`).join('');
        const salaryBadge = job.salary_estimation && job.salary_estimation !== 'Not provided'
            ? `<span class="badge badge-salary">💰 ${escapeHTML(job.salary_estimation)}</span>`
            : '';

        return `
            <article class="job-card">
                <div class="card-top">
                    <div class="job-header">
                        <h3 class="job-title">${escapeHTML(job.title)}</h3>
                    </div>
                    <div class="job-company">🏢 ${escapeHTML(job.company)}</div>

                    <div class="badge-row">
                        <span class="badge badge-loc">📍 ${escapeHTML(job.location)}</span>
                        <span class="badge ${bsClass}">${bsLabel}</span>
                        ${salaryBadge}
                    </div>

                    ${job.summary ? `<div class="job-summary">“${escapeHTML(job.summary)}”</div>` : ''}

                    ${techTags ? `
                        <div class="tech-stack-section">
                            <div class="tech-stack-title">Technologies clé</div>
                            <div class="tech-tags">${techTags}</div>
                        </div>
                    ` : ''}
                </div>

                <div class="card-footer">
                    <span class="post-date">${job.date_posted ? 'Publié le ' + escapeHTML(job.date_posted) : 'Récemment'}</span>
                    <a href="${escapeHTML(job.url)}" target="_blank" rel="noopener noreferrer" class="btn-apply">
                        Voir l'offre ↗
                    </a>
                </div>
            </article>
        `;
    }

    function escapeHTML(str) {
        if (!str) return '';
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }
});
