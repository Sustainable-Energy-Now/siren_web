/**
 * Infrastructure Network Diagram using D3.js v7
 * Full-network view of terminals, grid lines, and facilities
 * with pipeline status coloring, probability opacity, and bottleneck detection.
 */
class InfrastructureNetworkDiagram {
    constructor(containerId, data) {
        this.containerId = containerId;
        this.data = data;
        this.width = 800;
        this.height = 700;

        if (!data.nodes || !Array.isArray(data.nodes)) {
            throw new Error('Invalid data: nodes array is required');
        }
        if (!data.links || !Array.isArray(data.links)) {
            throw new Error('Invalid data: links array is required');
        }

        // Status color palette
        this.statusColors = {
            proposed: '#9e9e9e',
            planned: '#2196f3',
            under_construction: '#ff9800',
            commissioned: '#4caf50',
            decommissioned: '#f44336'
        };

        // Technology colors (for fallback)
        this.technologyColors = {
            'Solar': '#FDB462',
            'Wind': '#80B1D3',
            'Battery': '#FB8072',
            'Storage': '#FB8072',
            'Gas': '#BEBADA',
            'Coal': '#8DD3C7',
            'Hydro': '#FFFFB3',
            'Biomass': '#B3DE69',
            'Unknown': '#ffc107'
        };

        // Line type styling
        this.lineTypeStyles = {
            transmission: {color: '#198754', width: 4},
            subtransmission: {color: '#17a2b8', width: 2.5},
            distribution: {color: '#6c757d', width: 1.5}
        };

        // Scales
        const maxCapacity = d3.max(data.nodes.filter(n => n.type === 'facility'), d => d.capacity) || 100;
        const maxTransformer = d3.max(data.nodes.filter(n => n.type === 'terminal'), d => d.transformer_capacity) || 500;

        this.facilityScale = d3.scaleSqrt()
            .domain([0, maxCapacity])
            .range([6, 25]);

        this.terminalScale = d3.scaleSqrt()
            .domain([0, maxTransformer])
            .range([15, 35]);

        this.voltageScale = d3.scaleLinear()
            .domain([0, d3.max(data.links, d => d.voltage) || 500])
            .range([1, 6]);

        // Active status filters (all enabled by default)
        this.activeStatuses = new Set(['proposed', 'planned', 'under_construction', 'commissioned', 'decommissioned']);

        this.init();
    }

    init() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            throw new Error(`Container element '${this.containerId}' not found`);
        }

        this.width = container.clientWidth || 800;
        this.height = container.clientHeight || 700;

        // Create SVG
        this.svg = d3.select(`#${this.containerId}`)
            .append('svg')
            .attr('width', this.width)
            .attr('height', this.height);

        // Zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.05, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });
        this.svg.call(zoom);

        // Main group
        this.g = this.svg.append('g');

        // Arrow markers
        this.createArrowMarkers();

        // Force simulation - tuned for larger graph
        this.simulation = d3.forceSimulation(this.data.nodes)
            .force('link', d3.forceLink(this.data.links)
                .id(d => d.id)
                .distance(d => {
                    if (d.type === 'gridline') return 180;
                    return 100;
                }))
            .force('charge', d3.forceManyBody()
                .strength(d => {
                    if (d.type === 'terminal') return -800;
                    if (d.type === 'facility') return -200;
                    return -400;
                }))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('x', d3.forceX(this.width / 2).strength(0.03))
            .force('y', d3.forceY(this.height / 2).strength(0.03))
            .force('collision', d3.forceCollide()
                .radius(d => {
                    if (d.type === 'terminal') return this.terminalScale(d.transformer_capacity || 0) + 5;
                    if (d.type === 'facility') return this.facilityScale(d.capacity || 0) + 3;
                    return 15;
                }));

        // Draw layers
        this.linksGroup = this.g.append('g').attr('class', 'links');
        this.drawLinks();

        this.nodesGroup = this.g.append('g').attr('class', 'nodes');
        this.drawNodes();

        this.labelsGroup = this.g.append('g').attr('class', 'labels');
        this.drawLabels();

        this.simulation.on('tick', () => this.tick());
    }

    createArrowMarkers() {
        const defs = this.svg.append('defs');

        Object.entries(this.lineTypeStyles).forEach(([type, style]) => {
            defs.append('marker')
                .attr('id', `arrow-${type}`)
                .attr('viewBox', '0 -5 10 10')
                .attr('refX', 40)
                .attr('refY', 0)
                .attr('markerWidth', 4)
                .attr('markerHeight', 4)
                .attr('orient', 'auto')
                .append('path')
                .attr('d', 'M0,-5L10,0L0,5')
                .attr('fill', style.color);
        });
    }

    drawLinks() {
        this.links = this.linksGroup.selectAll('line')
            .data(this.data.links)
            .join('line')
            .attr('class', d => `link ${d.type}`)
            .attr('stroke', d => {
                if (d.type === 'gridline') {
                    const style = this.lineTypeStyles[d.line_type];
                    return style ? style.color : '#6c757d';
                }
                return d.is_primary ? '#198754' : '#aaa';
            })
            .attr('stroke-width', d => {
                if (d.type === 'gridline') {
                    const style = this.lineTypeStyles[d.line_type];
                    return style ? style.width : 1.5;
                }
                return d.is_primary ? 1.5 : 0.8;
            })
            .attr('stroke-dasharray', d => {
                if (d.type === 'facility_connection' && !d.is_primary) return '4,4';
                return 'none';
            })
            .attr('marker-end', d => {
                if (d.type === 'gridline') return `url(#arrow-${d.line_type || 'transmission'})`;
                return 'none';
            })
            .attr('opacity', 0.6);

        this.links.append('title')
            .text(d => {
                if (d.type === 'gridline') {
                    return `${d.label}\n${d.voltage} kV | ${d.capacity} MW\nType: ${d.line_type}`;
                }
                return `Connection: ${d.capacity} MW${d.is_primary ? ' (Primary)' : ''}`;
            });
    }

    drawNodes() {
        this.nodes = this.nodesGroup.selectAll('circle')
            .data(this.data.nodes)
            .join('circle')
            .attr('class', d => `node ${d.type}`)
            .attr('r', d => {
                if (d.type === 'terminal') return this.terminalScale(d.transformer_capacity || 0);
                if (d.type === 'facility') return this.facilityScale(d.capacity || 0);
                return 10;
            })
            .attr('fill', d => {
                if (d.type === 'terminal') return '#495057';
                if (d.type === 'facility') {
                    return this.statusColors[d.status] || '#9e9e9e';
                }
                return '#6c757d';
            })
            .attr('fill-opacity', d => {
                if (d.type === 'facility') {
                    return Math.max(0.3, d.commissioning_probability || 1.0);
                }
                return 1.0;
            })
            .attr('stroke', d => {
                if (d.type === 'terminal' && d.is_bottleneck) return '#f44336';
                if (d.type === 'terminal') return '#fff';
                return '#fff';
            })
            .attr('stroke-width', d => {
                if (d.type === 'terminal' && d.is_bottleneck) return 4;
                if (d.type === 'terminal') return 2;
                return 1;
            })
            .call(this.drag());

        this.nodes.append('title')
            .text(d => {
                if (d.type === 'terminal') {
                    let text = `${d.label}\n${d.voltage} kV\nTransformer: ${d.transformer_capacity} MVA\nConnected: ${d.total_connected_capacity} MW\nUtilization: ${d.utilization_percent}%`;
                    if (d.is_bottleneck) text += '\n*** BOTTLENECK ***';
                    return text;
                }
                if (d.type === 'facility') {
                    return `${d.label}\n${d.technology}\n${d.capacity} MW\nStatus: ${d.status}\nProbability: ${(d.commissioning_probability * 100).toFixed(0)}%`;
                }
                return d.label;
            });
    }

    drawLabels() {
        // Only label terminals (too many facilities would be cluttered)
        const terminalNodes = this.data.nodes.filter(d => d.type === 'terminal');

        this.labels = this.labelsGroup.selectAll('text')
            .data(terminalNodes)
            .join('text')
            .attr('class', 'node-label')
            .attr('text-anchor', 'middle')
            .attr('dy', d => this.terminalScale(d.transformer_capacity || 0) + 14)
            .style('font-size', '10px')
            .style('font-weight', 'bold')
            .style('fill', '#333')
            .style('pointer-events', 'none')
            .text(d => d.label.length > 18 ? d.label.substring(0, 18) + '...' : d.label);
    }

    tick() {
        this.links
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        this.nodes
            .attr('cx', d => d.x)
            .attr('cy', d => d.y);

        this.labels
            .attr('x', d => d.x)
            .attr('y', d => d.y);
    }

    drag() {
        return d3.drag()
            .on('start', (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on('drag', (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on('end', (event, d) => {
                if (!event.active) this.simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            });
    }

    highlightNode(nodeId) {
        this.resetHighlight();

        const connectedNodeIds = new Set([nodeId]);
        const connectedLinkIndices = new Set();

        this.data.links.forEach((link, index) => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
            if (sourceId === nodeId || targetId === nodeId) {
                connectedNodeIds.add(sourceId);
                connectedNodeIds.add(targetId);
                connectedLinkIndices.add(index);
            }
        });

        this.nodes.style('opacity', d => connectedNodeIds.has(d.id) ? 1 : 0.1);
        this.links.style('opacity', (d, i) => connectedLinkIndices.has(i) ? 0.8 : 0.05);
        this.labels.style('opacity', d => connectedNodeIds.has(d.id) ? 1 : 0.1);
    }

    resetHighlight() {
        this.nodes
            .style('opacity', d => {
                if (d.type === 'facility') return Math.max(0.3, d.commissioning_probability || 1.0);
                return 1;
            });
        this.links.style('opacity', 0.6);
        this.labels.style('opacity', 1);
    }

    filterByStatus(statuses) {
        this.activeStatuses = new Set(statuses);

        this.nodes
            .attr('display', d => {
                if (d.type === 'terminal') return 'block';
                return this.activeStatuses.has(d.status) ? 'block' : 'none';
            });

        // Hide links to hidden facilities
        this.links
            .attr('display', d => {
                const sourceId = typeof d.source === 'object' ? d.source.id : d.source;
                const targetId = typeof d.target === 'object' ? d.target.id : d.target;
                const sourceNode = this.data.nodes.find(n => n.id === sourceId);
                const targetNode = this.data.nodes.find(n => n.id === targetId);
                if (sourceNode && sourceNode.type === 'facility' && !this.activeStatuses.has(sourceNode.status)) return 'none';
                if (targetNode && targetNode.type === 'facility' && !this.activeStatuses.has(targetNode.status)) return 'none';
                return 'block';
            });

        this.labels.attr('display', 'block');
    }
}
