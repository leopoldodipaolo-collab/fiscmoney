
    function getOrCreateFiscTooltip(tooltipId) {
        let tooltipEl = document.getElementById(tooltipId);
        if (!tooltipEl) {
            tooltipEl = document.createElement('div');
            tooltipEl.id = tooltipId;
            tooltipEl.className = 'fisc-chart-tooltip';
            tooltipEl.style.display = 'none';
            tooltipEl.style.opacity = '0';
            document.body.appendChild(tooltipEl);
            
            tooltipEl.addEventListener('click', function(e) { e.stopPropagation(); });
            tooltipEl.addEventListener('touchstart', function(e) { e.stopPropagation(); }, { passive: true });
        }
        return tooltipEl;
    }

    function closeFiscTooltip(tooltipId, event) {
        if (event) {
            event.stopPropagation();
            if (event.preventDefault) event.preventDefault();
        }
        const tooltipEl = document.getElementById(tooltipId);
        if (tooltipEl) {
            tooltipEl.style.opacity = '0';
            tooltipEl.style.display = 'none';
            tooltipEl.dataset.closedByUser = 'true';
        }
    }

    function createFiscTooltipHandler(tooltipId) {
        return function(context) {
            const { chart, tooltip } = context;
            const tooltipEl = getOrCreateFiscTooltip(tooltipId);

            if (tooltip.opacity === 0) {
                if (tooltipEl.dataset.closedByUser !== 'true') {
                    if (!('ontouchstart' in window)) {
                        tooltipEl.style.opacity = '0';
                        tooltipEl.style.display = 'none';
                    }
                }
                return;
            }

            const currentDataIndex = tooltip.dataPoints && tooltip.dataPoints[0] ? tooltip.dataPoints[0].dataIndex : -1;
            if (tooltipEl.dataset.lastIndex !== String(currentDataIndex)) {
                tooltipEl.dataset.closedByUser = 'false';
                tooltipEl.dataset.lastIndex = String(currentDataIndex);
            }

            if (tooltipEl.dataset.closedByUser === 'true') {
                return;
            }

            if (tooltip.body) {
                const titleLines = tooltip.title || [];
                const bodyLines = tooltip.body.map(b => b.lines);
                const afterBodyLines = tooltip.afterBody || [];

                let html = '<div class="fisc-tt-header">';
                html += '<div class="fisc-tt-title">' + (titleLines.join(' ') || 'Dettaglio') + '</div>';
                html += `<button type="button" class="fisc-tt-close" onclick="closeFiscTooltip('${tooltipId}', event)" title="Chiudi finestra">&times;</button>`;
                html += '</div>';

                bodyLines.forEach(function(body, i) {
                    const colors = tooltip.labelColors && tooltip.labelColors[i];
                    let bg = colors ? (colors.borderColor || colors.backgroundColor) : '#38bdf8';
                    if (bg === 'rgba(0,0,0,0)' || bg === 'transparent') {
                        bg = colors.borderColor || '#38bdf8';
                    }
                    let dot = `<span class="fisc-tt-dot" style="background:${bg}"></span>`;
                    html += `<div class="fisc-tt-row">${dot}<span>${body}</span></div>`;
                });
                html += '</div>';

                if (afterBodyLines.length > 0) {
                    html += '<div class="fisc-tt-footer">';
                    afterBodyLines.forEach(function(line) {
                        if (line && !line.startsWith('---')) {
                            html += `<div>${line}</div>`;
                        }
                    });
                    html += '</div>';
                }

                tooltipEl.innerHTML = html;
            }

            tooltipEl.style.display = 'block';
            tooltipEl.style.opacity = '1';

            const canvasRect = chart.canvas.getBoundingClientRect();
            const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
            const scrollY = window.pageYOffset || document.documentElement.scrollTop;

            const ttWidth = tooltipEl.offsetWidth || 230;
            const ttHeight = tooltipEl.offsetHeight || 130;

            let left = canvasRect.left + scrollX + tooltip.caretX - (ttWidth / 2);
            let top = canvasRect.top + scrollY + tooltip.caretY - ttHeight - 10;

            const padding = 10;
            if (left < padding) left = padding;
            if (left + ttWidth > window.innerWidth - padding) {
                left = window.innerWidth - ttWidth - padding;
            }

            if (top < scrollY + padding) {
                top = canvasRect.top + scrollY + tooltip.caretY + 12;
            }

            tooltipEl.style.left = left + 'px';
            tooltipEl.style.top = top + 'px';
        };
    }

    document.addEventListener('click', function(e) {
        if (!e.target.closest('.fisc-chart-tooltip') && !e.target.closest('canvas')) {
            document.querySelectorAll('.fisc-chart-tooltip').forEach(el => {
                el.style.opacity = '0';
                el.style.display = 'none';
            });
        }
    });
    document.addEventListener('touchstart', function(e) {
        if (!e.target.closest('.fisc-chart-tooltip') && !e.target.closest('canvas')) {
            document.querySelectorAll('.fisc-chart-tooltip').forEach(el => {
                el.style.opacity = '0';
                el.style.display = 'none';
            });
        }
    }, { passive: true });
    