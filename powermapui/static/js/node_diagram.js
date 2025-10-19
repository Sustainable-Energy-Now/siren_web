/**
 * Node Diagram Visualization using D3.js
 * For displaying terminal, grid line, and facility connections
 * 
 * Place this file in: your_app/static/js/node_diagram.js
 */

class TerminalNetworkDiagram {
    constructor(containerId, data) {
        this.container = d3.select(`#${containerId}`);
        this.data = data;
        this.width = this.container.node().getBoundingClientRect().width;
        this.height = 600;
        
        // Color scheme
        this.colors = {
            terminal: '#0d6efd',     // Blue
            gridline: '#198754',     // Green
            facility: '#ffc107',     // Yellow/Gold
            outgoing: '#198754',     // Green
            incoming: '#0dcaf0',     // Cyan
        };
        
        this.init();
    }
    
    init() {
        // Clear any existing content
        this.container.selectAll('*').remove();
        
        // Create SVG
        this.svg = this.container.append('svg')
            .attr('width', this.width)
            .attr('height', this.height)
            .style('background-color', '#f8f9fa');
        
        // Create groups for different layers (order matters for z-index)
        this.linksGroup = this.svg.append('g').attr('class', 'links');
        this.nodesGroup = this.svg.append('g').attr('class', 'nodes');
        this.labelsGroup = this.svg.append('g').attr('class', 'labels');
        
        // Create zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.3, 4])
            .on('zoom', (event) => {
                this.linksGroup.attr('transform', event.transform);
                this.nodesGroup.attr('transform', event.transform);
                this.labelsGroup.attr('transform', event.transform);
            });
        
        this.svg.call(zoom);
        
        // Add zoom controls hint
        this.svg.append('text')
            .attr('x', 10)
            .attr('y', this.height - 10)
            .attr('class', 'zoom-hint')
            .style('font-size', '11px')
            .style('fill', '#6c757d')
            .text('Scroll to zoom • Drag to pan • Click & drag nodes');
        
        // Process data and create visualization
        this.processData();
        this.createForceSimulation();
        this.render();
        this.createLegend();
    }
    
    processData() {
        // Convert data to D3 format
        this.nodes = this.data.nodes.map(node => ({
            id: node.id,
            label: node.label,
            type: node.type,
            ...node
        }));
        
        this.links = this.data.links.map(link => ({
            source: link.source,
            target: link.target,
            ...link
        }));
    }
    
    createForceSimulation() {
        // Create force simulation
        this.simulation = d3.forceSimulation(this.nodes)
            .force('link', d3.forceLink(this.links)
                .id(d => d.id)
                .distance(d => {
                    // Adjust distance based on node types
                    const source = this.nodes.find(n => n.id === d.source.id);
                    const target = this.nodes.find(n => n.id === d.target.id);
                    
                    if (source.type === 'terminal' || target.type === 'terminal') {
                        return 150;
                    } else if (source.type === 'gridline' || target.type === 'gridline') {
                        return 100;
                    }
                    return 80;
                })
            )
            .force('charge', d3.forceManyBody()
                .strength(d => {
                    // Terminals repel more strongly
                    if (d.type === 'terminal') return -400;
                    if (d.type === 'gridline') return -250;
                    return -180;
                })
            )
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide().radius(d => {
                if (d.type === 'terminal') return 45;
                if (d.type === 'gridline') return 35;
                return 28;
            }));
    }
    
    render() {
        // Render links
        const link = this.linksGroup.selectAll('line')
            .data(this.links)
            .enter().append('line')
            .attr('stroke', d => {
                if (d.direction === 'outgoing') return this.colors.outgoing;
                if (d.direction === 'incoming') return this.colors.incoming;
                return '#999';
            })
            .attr('stroke-width', d => d.is_primary ? 3 : 2)
            .attr('stroke-opacity', 0.6)
            .attr('stroke-dasharray', d => d.is_primary ? '0' : '5,5')
            .attr('marker-end', d => {
                // Optional: Add arrow markers
                return '';
            });
        
        // Render nodes
        const node = this.nodesGroup.selectAll('circle')
            .data(this.nodes)
            .enter().append('circle')
            .attr('r', d => {
                if (d.type === 'terminal') return 20;
                if (d.type === 'gridline') return 15;
                return 12;
            })
            .attr('fill', d => this.colors[d.type] || '#999')
            .attr('stroke', '#fff')
            .attr('stroke-width', 2)
            .style('cursor', 'pointer')
            .call(this.createDragBehavior());
        
        // Add node labels
        const label = this.labelsGroup.selectAll('text')
            .data(this.nodes)
            .enter().append('text')
            .text(d => d.label)
            .attr('font-size', d => d.type === 'terminal' ? 12 : 10)
            .attr('font-weight', d => d.type === 'terminal' ? 'bold' : 'normal')
            .attr('text-anchor', 'middle')
            .attr('dy', d => {
                if (d.type === 'terminal') return 35;
                if (d.type === 'gridline') return 25;
                return 20;
            })
            .attr('fill', '#212529')
            .style('pointer-events', 'none')
            .style('user-select', 'none');
        
        // Add tooltips
        node.append('title')
            .text(d => this.getTooltipText(d));
        
        // Store references for event handlers
        this.nodeElements = node;
        this.linkElements = link;
        this.labelElements = label;
        
        // Update positions on each tick
        this.simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);
            
            node
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);
            
            label
                .attr('x', d => d.x)
                .attr('y', d => d.y);
        });
    }
    
    createDragBehavior() {
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
    
    getTooltipText(node) {
        let text = `${node.label}\nType: ${node.type}`;
        
        if (node.voltage) {
            text += `\nVoltage: ${node.voltage} kV`;
        }
        if (node.capacity) {
            text += `\nCapacity: ${node.capacity} MW`;
        }
        if (node.technology) {
            text += `\nTechnology: ${node.technology}`;
        }
        
        return text;
    }
    
    createLegend() {
        const legend = this.svg.append('g')
            .attr('class', 'legend')
            .attr('transform', `translate(20, 20)`);
        
        const legendData = [
            { label: 'Terminal', color: this.colors.terminal, type: 'node', radius: 20 },
            { label: 'Grid Line', color: this.colors.gridline, type: 'node', radius: 15 },
            { label: 'Facility', color: this.colors.facility, type: 'node', radius: 12 },
            { label: 'Outgoing', color: this.colors.outgoing, type: 'line' },
            { label: 'Incoming', color: this.colors.incoming, type: 'line' },
        ];
        
        const legendItem = legend.selectAll('.legend-item')
            .data(legendData)
            .enter().append('g')
            .attr('class', 'legend-item')
            .attr('transform', (d, i) => `translate(0, ${i * 28})`);
        
        // Add shapes
        legendItem.each(function(d) {
            if (d.type === 'node') {
                d3.select(this).append('circle')
                    .attr('r', d.radius / 2.5)
                    .attr('cx', 10)
                    .attr('cy', 0)
                    .attr('fill', d.color)
                    .attr('stroke', '#fff')
                    .attr('stroke-width', 2);
            } else {
                d3.select(this).append('line')
                    .attr('x1', 0)
                    .attr('y1', 0)
                    .attr('x2', 20)
                    .attr('y2', 0)
                    .attr('stroke', d.color)
                    .attr('stroke-width', 3);
            }
        });
        
        // Add labels
        legendItem.append('text')
            .attr('x', 25)
            .attr('y', 5)
            .text(d => d.label)
            .attr('font-size', 12)
            .attr('fill', '#212529');
        
        // Add background
        const bbox = legend.node().getBBox();
        legend.insert('rect', ':first-child')
            .attr('x', bbox.x - 10)
            .attr('y', bbox.y - 10)
            .attr('width', bbox.width + 20)
            .attr('height', bbox.height + 20)
            .attr('fill', 'white')
            .attr('opacity', 0.95)
            .attr('rx', 5)
            .attr('stroke', '#dee2e6')
            .attr('stroke-width', 1);
    }
    
    // Public methods
    
    highlightNode(nodeId) {
        // Dim all nodes and links
        this.nodeElements.style('opacity', d => d.id === nodeId ? 1 : 0.2);
        this.labelElements.style('opacity', d => d.id === nodeId ? 1 : 0.2);
        
        // Highlight connected links
        this.linkElements.style('opacity', d => {
            if (d.source.id === nodeId || d.target.id === nodeId) {
                // Also highlight connected nodes
                this.nodeElements.style('opacity', function(n) {
                    if (n.id === d.source.id || n.id === d.target.id) {
                        return 1;
                    }
                    return d3.select(this).style('opacity');
                });
                return 0.8;
            }
            return 0.1;
        });
    }
    
    resetHighlight() {
        this.nodeElements.style('opacity', 1);
        this.linkElements.style('opacity', 0.6);
        this.labelElements.style('opacity', 1);
    }
    
    destroy() {
        this.simulation.stop();
        this.container.selectAll('*').remove();
    }
    
    // Export as image
    exportAsSVG() {
        const svgElement = this.svg.node();
        const serializer = new XMLSerializer();
        const svgString = serializer.serializeToString(svgElement);
        return svgString;
    }
}

// Make it available globally
if (typeof window !== 'undefined') {
    window.TerminalNetworkDiagram = TerminalNetworkDiagram;
}