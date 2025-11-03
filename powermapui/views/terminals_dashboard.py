"""
Dashboard view for terminal network overview
"""
from django.shortcuts import render
from django.db.models import Q
from siren_web.models import Terminals, GridLines, FacilityGridConnections
from .terminal_utilities import (
    get_system_wide_terminal_statistics,
    get_terminal_statistics,
)

def terminals_dashboard(request):
    """
    Dashboard showing overview of all terminals and their connections
    """
    # Get system-wide statistics
    system_stats = get_system_wide_terminal_statistics()
    
    # Get top terminals by various metrics
    terminals = Terminals.objects.filter(active=True)
    
    # Top terminals by connected capacity
    terminal_capacity_data = []
    for terminal in terminals:
        stats = get_terminal_statistics(terminal)
        terminal_capacity_data.append({
            'terminal': terminal,
            'capacity': stats['total_facility_capacity'],
            'facilities_count': stats['connected_facilities_count'],
            'lines_count': stats['total_lines'],
            'utilization': stats['utilization_percent'],
        })
    
    terminal_capacity_data.sort(key=lambda x: x['capacity'], reverse=True)
    top_terminals_by_capacity = terminal_capacity_data[:10]
    
    # Top terminals by utilization
    terminal_capacity_data.sort(key=lambda x: x['utilization'], reverse=True)
    top_terminals_by_utilization = [t for t in terminal_capacity_data if t['utilization'] > 0][:10]
    
    # Get terminals needing attention
    high_utilization_terminals = [
        t for t in terminal_capacity_data 
        if t['utilization'] > 80
    ]
    
    unconnected_terminals = [
        t for t in terminal_capacity_data 
        if t['lines_count'] == 0
    ]
    
    # Grid line statistics
    all_grid_lines = GridLines.objects.filter(active=True)
    connected_grid_lines = all_grid_lines.filter(
        Q(from_terminal__isnull=False) | Q(to_terminal__isnull=False)
    )
    unconnected_grid_lines = all_grid_lines.filter(
        from_terminal__isnull=True,
        to_terminal__isnull=True
    )
    
    # Technology breakdown across all terminals
    tech_breakdown = {}
    for terminal in terminals:
        for line in terminal.get_connected_grid_lines():
            connections = FacilityGridConnections.objects.filter(
                idgridlines=line,
                active=True
            ).select_related('idfacilities__idtechnologies')
            
            for conn in connections:
                if conn.idfacilities.idtechnologies:
                    tech_name = conn.idfacilities.idtechnologies.technology_name
                    if tech_name not in tech_breakdown:
                        tech_breakdown[tech_name] = {
                            'count': 0,
                            'capacity': 0,
                        }
                    tech_breakdown[tech_name]['count'] += 1
                    if conn.idfacilities.capacity:
                        tech_breakdown[tech_name]['capacity'] += conn.idfacilities.capacity
    
    context = {
        'system_stats': system_stats,
        'top_terminals_by_capacity': top_terminals_by_capacity,
        'top_terminals_by_utilization': top_terminals_by_utilization,
        'high_utilization_terminals': high_utilization_terminals,
        'unconnected_terminals': unconnected_terminals,
        'total_grid_lines': all_grid_lines.count(),
        'connected_grid_lines': connected_grid_lines.count(),
        'unconnected_grid_lines': unconnected_grid_lines.count(),
        'tech_breakdown': tech_breakdown,
    }
    
    return render(request, 'terminals/dashboard.html', context)

def terminal_health_check(request):
    """
    Check health and potential issues of all terminals
    """
    issues = {
        'critical': [],
        'warning': [],
        'info': [],
    }
    
    terminals = Terminals.objects.filter(active=True)
    
    for terminal in terminals:
        stats = get_terminal_statistics(terminal)
        
        # Critical issues
        if stats['utilization_percent'] > 95:
            issues['critical'].append({
                'terminal': terminal,
                'issue': 'Over-capacity',
                'details': f"Utilization at {stats['utilization_percent']:.1f}%",
            })
        
        if stats['total_lines'] == 0:
            issues['critical'].append({
                'terminal': terminal,
                'issue': 'No connections',
                'details': 'Terminal has no grid line connections',
            })
        
        # Warnings
        if stats['utilization_percent'] > 80 and stats['utilization_percent'] <= 95:
            issues['warning'].append({
                'terminal': terminal,
                'issue': 'High utilization',
                'details': f"Utilization at {stats['utilization_percent']:.1f}%",
            })
        
        if stats['outgoing_lines_count'] == 0 and stats['incoming_lines_count'] > 0:
            issues['warning'].append({
                'terminal': terminal,
                'issue': 'No outgoing lines',
                'details': 'Terminal has only incoming connections',
            })
        
        if stats['incoming_lines_count'] == 0 and stats['outgoing_lines_count'] > 0:
            issues['warning'].append({
                'terminal': terminal,
                'issue': 'No incoming lines',
                'details': 'Terminal has only outgoing connections',
            })
        
        # Info
        if stats['connected_facilities_count'] > 20:
            issues['info'].append({
                'terminal': terminal,
                'issue': 'Many facilities',
                'details': f"{stats['connected_facilities_count']} facilities connected",
            })
    
    context = {
        'critical_issues': issues['critical'],
        'warning_issues': issues['warning'],
        'info_items': issues['info'],
        'total_critical': len(issues['critical']),
        'total_warning': len(issues['warning']),
        'total_info': len(issues['info']),
    }
    
    return render(request, 'terminals/health_check.html', context)

def export_terminal_data(request, pk):
    """
    Export terminal data in various formats
    """
    from django.http import JsonResponse, HttpResponse
    import csv
    
    terminal = Terminals.objects.get(pk=pk)
    format_type = request.GET.get('format', 'json')
    
    if format_type == 'json':
        from .terminal_utilities import export_terminal_topology_json
        data = export_terminal_topology_json(terminal)
        return JsonResponse(data, safe=False)
    
    elif format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="terminal_{terminal.pk}_data.csv"'
        
        writer = csv.writer(response)
        
        # Write terminal info
        writer.writerow(['Terminal Information'])
        writer.writerow(['Name', terminal.terminal_name])
        writer.writerow(['Code', terminal.terminal_code])
        writer.writerow(['Voltage', f"{terminal.primary_voltage_kv} kV"])
        writer.writerow([])
        
        # Write grid lines
        writer.writerow(['Connected Grid Lines'])
        writer.writerow(['Line Name', 'Voltage (kV)', 'Capacity (MW)', 'Length (km)', 'Direction'])
        
        for line in terminal.get_connected_grid_lines():
            direction = 'Outgoing' if line.from_terminal == terminal else 'Incoming'
            writer.writerow([
                line.line_name,
                line.voltage_level,
                line.thermal_capacity_mw,
                line.length_km,
                direction,
            ])
        
        writer.writerow([])
        
        # Write facilities
        writer.writerow(['Connected Facilities'])
        writer.writerow(['Facility Name', 'Technology', 'Capacity (MW)', 'Via Grid Line'])
        
        for line in terminal.get_connected_grid_lines():
            connections = FacilityGridConnections.objects.filter(
                idgridlines=line,
                active=True
            ).select_related('idfacilities', 'idfacilities__idtechnologies')
            
            for conn in connections:
                writer.writerow([
                    conn.idfacilities.facility_name,
                    conn.idfacilities.idtechnologies.technology_name if conn.idfacilities.idtechnologies else 'N/A',
                    conn.idfacilities.capacity or 'N/A',
                    line.line_name,
                ])
        
        return response
    
    else:
        return JsonResponse({'error': 'Invalid format'}, status=400)