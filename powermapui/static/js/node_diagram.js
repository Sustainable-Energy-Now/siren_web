/**
 * Terminal Network Diagram using D3.js v7
 * Visualizes terminals, grid lines, and facilities
 */
class TerminalNetworkDiagram {
    constructor(containerId, data) {
        this.containerId = containerId;
        this.data = data;
        this.width = 800;
        this.height = 600;
        
        // Validate data structure
        if (!data.nodes || !Array.isArray(data.nodes)) {
            throw new Error('Invalid data: nodes array is required');
        }
        if (!data.links || !Array.isArray(data.links)) {
            throw new Error('Invalid data: links array is required');
        }
        
        console.log(`Data validated: ${data.nodes.length} nodes, ${data.links.length} links`);
        
        // Scales for sizing
        const maxVoltage = d3.max(data.links, d => d.voltage) || 500;
        const maxCapacity = d3.max(data.nodes.filter(n => n.type === 'facility'), d => d.capacity) || 100;
        
        console.log(`Max voltage: ${maxVoltage}, Max capacity: ${maxCapacity}`);
        
        this.voltageScale = d3.scaleLinear()
            .domain([0, maxVoltage])
            .range([1, 8]);
        
        this.capacityScale = d3.scaleSqrt()
            .domain([0, maxCapacity])
            .range([8, 30]);
        
        // Technology color scale
        this.technologyColors = {
            'Solar': '#FDB462',
            'Wind': '#80B1D3',
            'Battery': '#FB8072',
            'Gas': '#BEBADA',
            'Coal': '#8DD3C7',
            'Hydro': '#FFFFB3',
            'Biomass': '#B3DE69',
            'Diesel': '#FCCDE5',
            'Other': '#ffc107',
            'Unknown': '#ffc107'
        };
        
        this.init();
    }
    
    init() {
        console.log('Initializing diagram...');
        const container = document.getElementById(this.containerId);
        if (!container) {
            throw new Error(`Container element '${this.containerId}' not found`);
        }
        
        this.width = container.clientWidth || 800;
        this.height = container.clientHeight || 600;
        console.log(`Container dimensions: ${this.width}x${this.height}`);
        
        // Create SVG
        this.svg = d3.select(`#${this.containerId}`)
            .append('svg')
            .attr('width', this.width)
            .attr('height', this.height);
        
        console.log('SVG created');
        
        // Add zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });
        
        this.svg.call(zoom);
        
        // Main group for zooming/panning
        this.g = this.svg.append('g');
        
        console.log('Creating arrow markers...');
        // Create arrow markers for directed edges
        this.createArrowMarkers();
        
        console.log('Creating force simulation...');
        // Create force simulation
        this.simulation = d3.forceSimulation(this.data.nodes)
            .force('link', d3.forceLink(this.data.links)
                .id(d => d.id)
                .distance(d => {
                    if (d.type === 'gridline') return 200;
                    return 150;
                }))
            .force('charge', d3.forceManyBody()
                .strength(d => {
                    if (d.type === 'terminal') return -1000;
                    if (d.type === 'endpoint') return -600;
                    if (d.type === 'facility') return -300;
                    return -500;
                }))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide()
                .radius(d => {
                    if (d.type === 'terminal') return 40;
                    if (d.type === 'endpoint') return 25;
                    if (d.type === 'facility') return this.capacityScale(d.capacity || 0) + 5;
                    return 30;
                }));
        
        console.log('Drawing links...');
        // Draw links (grid lines and connections)
        this.linksGroup = this.g.append('g').attr('class', 'links');
        this.drawLinks();
        
        console.log('Drawing nodes...');
        // Draw nodes (terminals and facilities)
        this.nodesGroup = this.g.append('g').attr('class', 'nodes');
        this.drawNodes();
        
        console.log('Drawing labels...');
        // Add labels
        this.labelsGroup = this.g.append('g').attr('class', 'labels');
        this.drawLabels();
        
        console.log('Setting up tick handler...');
        // Update positions on each tick
        this.simulation.on('tick', () => this.tick());
        
        console.log('Diagram initialization complete');
    }
    
    createArrowMarkers() {
        const defs = this.svg.append('defs');
        
        // Arrow for outgoing gridlines
        defs.append('marker')
            .attr('id', 'arrow-outgoing')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 40)  // Position arrow outside the target node
            .attr('refY', 0)
            .attr('markerWidth', 5)
            .attr('markerHeight', 5)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#198754');
        
        // Arrow for incoming gridlines
        defs.append('marker')
            .attr('id', 'arrow-incoming')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 40)  // Position arrow outside the target node
            .attr('refY', 0)
            .attr('markerWidth', 5)
            .attr('markerHeight', 5)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#0dcaf0');
        
        // Create gradient for power flow animation
        const gradient = defs.append('linearGradient')
            .attr('id', 'power-flow-gradient')
            .attr('gradientUnits', 'userSpaceOnUse');
        
        gradient.append('stop')
            .attr('offset', '0%')
            .attr('stop-color', '#fff')
            .attr('stop-opacity', '0');
        
        gradient.append('stop')
            .attr('offset', '50%')
            .attr('stop-color', '#fff')
            .attr('stop-opacity', '0.8');
        
        gradient.append('stop')
            .attr('offset', '100%')
            .attr('stop-color', '#fff')
            .attr('stop-opacity', '0');
    }
    
    drawLinks() {
        console.log('Drawing links, total:', this.data.links.length);
        this.data.links.forEach((link, i) => {
            console.log(`Link ${i}:`, {
                source: link.source,
                target: link.target,
                type: link.type,
                direction: link.direction,
                voltage: link.voltage
            });
        });
        
        // Draw base links
        this.links = this.linksGroup.selectAll('line.base-link')
            .data(this.data.links)
            .join('line')
            .attr('class', d => `base-link link ${d.type}`)
            .attr('stroke', d => {
                if (d.type === 'gridline') {
                    const color = d.direction === 'outgoing' ? '#198754' : '#0dcaf0';
                    console.log(`Link ${d.gridline_name}: color=${color}, direction=${d.direction}`);
                    return color;
                }
                return d.is_primary ? '#198754' : '#999';
            })
            .attr('stroke-width', d => {
                if (d.type === 'gridline') {
                    const width = this.voltageScale(d.voltage || 0);
                    console.log(`Link ${d.gridline_name}: width=${width}, voltage=${d.voltage}`);
                    return width;
                }
                return d.is_primary ? 2 : 1;
            })
            .attr('stroke-dasharray', d => {
                if (d.type === 'gridline') return 'none';
                return d.is_primary ? 'none' : '5,5';
            })
            .attr('marker-end', d => {
                if (d.type === 'gridline') {
                    const marker = d.direction === 'outgoing' ? 'url(#arrow-outgoing)' : 'url(#arrow-incoming)';
                    console.log(`Link ${d.gridline_name}: marker=${marker}, direction=${d.direction}`);
                    return marker;
                }
                return 'none';
            })
            .attr('opacity', 0.7);
        
        // Add animated power flow overlay for gridlines
        this.flowLines = this.linksGroup.selectAll('line.flow-line')
            .data(this.data.links.filter(d => d.type === 'gridline'))
            .join('line')
            .attr('class', 'flow-line')
            .attr('stroke', 'rgba(255, 255, 255, 0.6)')
            .attr('stroke-width', d => this.voltageScale(d.voltage || 0) * 0.3)
            .attr('stroke-dasharray', '10,10')
            .attr('opacity', 0.8)
            .attr('pointer-events', 'none');
        
        // Animate the flow
        this.animatePowerFlow();
        
        console.log('Links created:', this.links.size());
        console.log('Flow lines created:', this.flowLines.size());
        
        // Add tooltips to links
        this.links.append('title')
            .text(d => {
                if (d.type === 'gridline') {
                    return `${d.gridline_name}\n${d.voltage} kV\n${d.capacity} MW capacity\nDirection: ${d.direction}`;
                }
                return `${d.gridline_name}\nConnection: ${d.capacity} MW\n${d.is_primary ? 'Primary' : 'Secondary'}`;
            });
    }
    
    animatePowerFlow() {
        if (!this.flowLines) return;
        
        const animate = () => {
            this.flowLines
                .attr('stroke-dashoffset', 0)
                .transition()
                .duration(2000)
                .ease(d3.easeLinear)
                .attr('stroke-dashoffset', -20)
                .on('end', animate);
        };
        
        animate();
    }
    
    drawNodes() {
        this.nodes = this.nodesGroup.selectAll('circle')
            .data(this.data.nodes)
            .join('circle')
            .attr('class', d => `node ${d.type}`)
            .attr('r', d => {
                if (d.type === 'terminal') {
                    return d.is_main ? 35 : 30;
                }
                if (d.type === 'endpoint') {
                    return 20;
                }
                if (d.type === 'facility') {
                    return this.capacityScale(d.capacity || 0);
                }
                return 20;
            })
            .attr('fill', d => {
                if (d.type === 'terminal') return d.is_main ? '#0d6efd' : '#6c757d';
                if (d.type === 'endpoint') return '#e9ecef';
                if (d.type === 'facility') {
                    // Get technology and return corresponding color
                    const tech = d.technology || 'Unknown';
                    // Try to match technology name (case insensitive, partial match)
                    for (const [key, color] of Object.entries(this.technologyColors)) {
                        if (tech.toLowerCase().includes(key.toLowerCase())) {
                            return color;
                        }
                    }
                    return this.technologyColors['Unknown'];
                }
                return '#6c757d';
            })
            .attr('stroke', d => {
                if (d.type === 'endpoint') return '#6c757d';
                return '#fff';
            })
            .attr('stroke-width', d => {
                if (d.type === 'endpoint') return 2;
                return d.is_main ? 4 : 2;
            })
            .attr('stroke-dasharray', d => {
                if (d.type === 'endpoint') return '3,3';
                return 'none';
            })
            .call(this.drag());
        
        // Add tooltips to nodes
        this.nodes.append('title')
            .text(d => {
                if (d.type === 'terminal') {
                    return `${d.label}\n${d.voltage} kV${d.is_main ? ' (Main)' : ''}`;
                }
                if (d.type === 'endpoint') {
                    return `${d.label}\n${d.voltage} kV\n(Incomplete connection)`;
                }
                if (d.type === 'facility') {
                    return `${d.label}\n${d.technology}\n${d.capacity} MW`;
                }
                return d.label;
            });
    }
    
    drawLabels() {
        this.labels = this.labelsGroup.selectAll('text')
            .data(this.data.nodes)
            .join('text')
            .attr('class', 'node-label')
            .attr('text-anchor', 'middle')
            .attr('dy', d => {
                if (d.type === 'terminal') return d.is_main ? 50 : 45;
                if (d.type === 'endpoint') return 35;
                if (d.type === 'facility') return this.capacityScale(d.capacity || 0) + 15;
                return 35;
            })
            .style('font-size', d => {
                if (d.type === 'terminal') return d.is_main ? '14px' : '12px';
                if (d.type === 'endpoint') return '11px';
                return '11px';
            })
            .style('font-weight', d => d.is_main ? 'bold' : 'normal')
            .style('font-style', d => d.type === 'endpoint' ? 'italic' : 'normal')
            .style('fill', d => d.type === 'endpoint' ? '#6c757d' : '#333')
            .style('pointer-events', 'none')
            .text(d => {
                // Truncate long labels
                if (d.label.length > 20) {
                    return d.label.substring(0, 20) + '...';
                }
                return d.label;
            });
    }
    
    tick() {
        // Update base links
        this.links
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        // Update flow lines
        if (this.flowLines) {
            this.flowLines
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);
        }
        
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
        // Reset all
        this.resetHighlight();
        
        // Find connected nodes and links
        const connectedNodeIds = new Set([nodeId]);
        const connectedLinkIndices = new Set();
        
        this.data.links.forEach((link, index) => {
            if (link.source.id === nodeId || link.target.id === nodeId) {
                connectedNodeIds.add(link.source.id);
                connectedNodeIds.add(link.target.id);
                connectedLinkIndices.add(index);
            }
        });
        
        // Dim non-connected elements
        this.nodes.style('opacity', d => connectedNodeIds.has(d.id) ? 1 : 0.2);
        this.links.style('opacity', (d, i) => connectedLinkIndices.has(i) ? 0.9 : 0.1);
        this.labels.style('opacity', d => connectedNodeIds.has(d.id) ? 1 : 0.2);
    }
    
    resetHighlight() {
        this.nodes.style('opacity', 1);
        this.links.style('opacity', 0.7);
        this.labels.style('opacity', 1);
    }
}