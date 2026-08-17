document.addEventListener('DOMContentLoaded', () => {
    // KPI Elements
    const kpiTotal = document.getElementById('kpi-total');
    const kpiRelevant = document.getElementById('kpi-relevant');
    const kpiFitScore = document.getElementById('kpi-fit-score');
    const kpiBsScore = document.getElementById('kpi-bs-score');
    
    // Filter Elements
    const filterSearch = document.getElementById('filter-search');
    const filterLocation = document.getElementById('filter-location');
    const filterFit = document.getElementById('filter-fit');
    const filterSort = document.getElementById('filter-sort');
    const filterBs = document.getElementById('filter-bs');
    const filterRelevant = document.getElementById('filter-relevant');
    const btnRefresh = document.getElementById('btn-refresh');

    // Tabs & Views
    const tabJobs = document.getElementById('tab-jobs');
    const tabTrends = document.getElementById('tab-trends');
    const viewJobs = document.getElementById('view-jobs');
    const viewTrends = document.getElementById('view-trends');
    
    // Grids & Badges
    const jobsGrid = document.getElementById('jobs-grid');
    const emptyState = document.getElementById('empty-state');
    const jobsCountBadge = document.getElementById('jobs-count-badge');
    const lastUpdateTime = document.getElementById('last-update-time');
    const regionTechGrid = document.getElementById('region-tech-grid');

    let debounceTimer;
    let chartSalaryLocInstance = null;
    let chartTopTechInstance = null;
    let chartLocationInstance = null;
    let chartBsTechInstance = null;

    // Load initial data
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
    filterFit.addEventListener('change', fetchJobs);
    filterSort.addEventListener('change', fetchJobs);
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
                kpiBsScore.innerHTML = `${(data.avg_bullshit_score || 0).toFixed(1)}<span class="kpi-sub">/10</span>`;
                kpiFitScore.innerHTML = `${(data.avg_fit_score || 0).toFixed(1)}<span class="kpi-sub">/10</span>`;
            }
        } catch (err) {
            console.error('Error fetching stats:', err);
        }
    }

    async function fetchJobs() {
        const search = filterSearch.value.trim();
        const location = filterLocation.value;
        const fitMin = filterFit.value;
        const sortBy = filterSort.value;
        const maxBs = filterBs.value;
        const relevantOnly = filterRelevant.checked;

        let queryParams = new URLSearchParams();
        if (search) queryParams.append('search', search);
        if (location && location !== 'all') queryParams.append('location', location);
        if (fitMin && fitMin !== 'all') queryParams.append('min_fit_score', fitMin);
        if (sortBy) queryParams.append('sort_by', sortBy);
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
                renderRegionalTechCards(data.tech_by_location || {});
                renderTrendsCharts(data);
            }
        } catch (err) {
            console.error('Error fetching trends:', err);
        }
    }

    function renderRegionalTechCards(techByLoc) {
        if (!regionTechGrid) return;

        const regions = [
            { key: 'Luxembourg', label: 'Luxembourg', flag: '🇱🇺', color: '#06b6d4' },
            { key: 'France', label: 'France', flag: '🇫🇷', color: '#8b5cf6' },
            { key: 'Remote', label: 'Full Remote', flag: '🌐', color: '#10b981' }
        ];

        let html = '';
        regions.forEach(reg => {
            const techList = techByLoc[reg.key] || [];
            const itemsHtml = techList.length > 0
                ? techList.map((t, idx) => `
                    <div class="reg-tech-item">
                        <span class="reg-tech-rank">#${idx + 1}</span>
                        <span class="reg-tech-name">${escapeHTML(t.name)}</span>
                        <span class="reg-tech-count">${t.count} offres</span>
                    </div>
                `).join('')
                : `<div class="reg-tech-empty">Aucune offre analysée pour cette zone</div>`;

            html += `
                <div class="region-card">
                    <div class="region-card-header" style="border-top-color: ${reg.color}">
                        <div class="region-flag-title">
                            <span class="region-flag">${reg.flag}</span>
                            <h4>${reg.label}</h4>
                        </div>
                        <span class="region-pill" style="background: ${reg.color}18; color: ${reg.color}; border: 1px solid ${reg.color}40;">Top 5</span>
                    </div>
                    <div class="region-tech-list">
                        ${itemsHtml}
                    </div>
                </div>
            `;
        });

        regionTechGrid.innerHTML = html;
    }

    function renderTrendsCharts(data) {
        if (typeof Chart === 'undefined') return;

        // Chart 1: Average Salaries by Location (Bar Chart)
        const salByLoc = data.avg_salary_by_location || {};
        const salLabels = ['Luxembourg', 'France', 'Remote'];
        const salValues = salLabels.map(loc => salByLoc[loc] || 0);

        const ctxSalary = document.getElementById('chart-salary-loc').getContext('2d');
        if (chartSalaryLocInstance) chartSalaryLocInstance.destroy();

        chartSalaryLocInstance = new Chart(ctxSalary, {
            type: 'bar',
            data: {
                labels: ['Luxembourg 🇱🇺', 'France 🇫🇷', 'Remote 🌐'],
                datasets: [{
                    label: 'Salaire Brut Moyen (€ / an)',
                    data: salValues,
                    backgroundColor: [
                        'rgba(6, 182, 212, 0.75)',
                        'rgba(139, 92, 246, 0.75)',
                        'rgba(16, 185, 129, 0.75)'
                    ],
                    borderColor: ['#06b6d4', '#8b5cf6', '#10b981'],
                    borderWidth: 1.5,
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.raw.toLocaleString('fr-FR')} € / an`
                        }
                    }
                },
                scales: {
                    x: { ticks: { color: '#9ca3af', font: { family: 'Inter', size: 12 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: {
                        ticks: {
                            color: '#9ca3af',
                            font: { family: 'Inter' },
                            callback: (v) => `${(v / 1000).toFixed(0)}k €`
                        },
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        beginAtZero: true
                    }
                }
            }
        });

        // Chart 2: Top Technologies Global (Bar Chart)
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
                    backgroundColor: 'rgba(139, 92, 246, 0.75)',
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
                    x: { ticks: { color: '#9ca3af', font: { family: 'Inter', size: 11 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { ticks: { color: '#9ca3af', font: { family: 'Inter' } }, grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true }
                }
            }
        });

        // Chart 3: Location Distribution (Doughnut Chart)
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

        // Chart 4: Bullshit Score by Tech (Bar Chart)
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
                    backgroundColor: bsValues.map(v => v >= 7 ? 'rgba(239, 68, 68, 0.75)' : v >= 4 ? 'rgba(245, 158, 11, 0.75)' : 'rgba(16, 185, 129, 0.75)'),
                    borderColor: 'rgba(255,255,255,0.15)',
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
                    x: { ticks: { color: '#9ca3af', font: { family: 'Inter', size: 11 } }, grid: { color: 'rgba(255,255,255,0.05)' } },
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
        // Fit Score calculation & color coding
        const fitScore = job.fit_score !== undefined && job.fit_score !== null ? job.fit_score : 1;
        let fitClass = 'fit-low';
        let fitText = 'Faible Match';
        let fitIcon = '🔴';
        
        if (fitScore >= 8) {
            fitClass = 'fit-high';
            fitText = 'Top Match';
            fitIcon = '🌟';
        } else if (fitScore >= 5) {
            fitClass = 'fit-medium';
            fitText = 'Match Modéré';
            fitIcon = '🟡';
        }

        // Bullshit Score calculation & color coding
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

        // Salary formatting
        let formattedSalary = job.salary_estimation || '';
        if (job.salary_min && job.salary_max) {
            const minK = Math.round(job.salary_min / 1000);
            const maxK = Math.round(job.salary_max / 1000);
            formattedSalary = `${minK}k€ - ${maxK}k€ / an`;
        } else if (job.salary_min) {
            formattedSalary = `Dès ${Math.round(job.salary_min / 1000)}k€ / an`;
        } else if (job.salary_max) {
            formattedSalary = `Jusqu'à ${Math.round(job.salary_max / 1000)}k€ / an`;
        }

        const salaryBadge = formattedSalary && formattedSalary !== 'Not provided' && formattedSalary !== 'Non communiqué'
            ? `<span class="badge badge-salary">💰 ${escapeHTML(formattedSalary)}</span>`
            : '';

        // Tech Stack Tags
        const techTags = (job.tech_stack || []).map(t => `<span class="tech-tag">${escapeHTML(t)}</span>`).join('');

        // Missing Skills Tags
        const missingSkills = job.missing_skills || [];
        const missingSkillsSection = missingSkills.length > 0 ? `
            <div class="missing-skills-section">
                <div class="missing-skills-title">⚠️ Compétences à acquérir :</div>
                <div class="missing-tags">
                    ${missingSkills.map(s => `<span class="missing-tag">${escapeHTML(s)}</span>`).join('')}
                </div>
            </div>
        ` : '';

        return `
            <article class="job-card ${fitScore >= 8 ? 'highlight-fit' : ''}">
                <div class="card-top">
                    <!-- Fit Score Meter Badge -->
                    <div class="fit-score-header">
                        <div class="fit-badge ${fitClass}">
                            <span class="fit-icon">${fitIcon}</span>
                            <span class="fit-val">${fitScore}/10</span>
                            <span class="fit-label">${fitText}</span>
                        </div>
                    </div>

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
                            <div class="tech-stack-title">Technologies requises</div>
                            <div class="tech-tags">${techTags}</div>
                        </div>
                    ` : ''}

                    ${missingSkillsSection}
                </div>

                <div class="card-footer">
                    <span class="post-date">${job.date_posted ? 'Publié le ' + escapeHTML(job.date_posted) : 'Récemment'}</span>
                    <a href="${escapeHTML(job.url)}" target="_blank" rel="noopener noreferrer" class="btn-apply">
                        Postuler ↗
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
