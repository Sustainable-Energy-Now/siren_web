# tests.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.apps import apps
from .models import SystemComponent, ComponentConnection
import json

class SystemComponentModelTests(TestCase):
    def setUp(self):
        self.component = SystemComponent.objects.create(
            name='test_component',
            display_name='Test Component',
            component_type='model',
            description='A test component',
            model_class_name='Technologies',
            position_x=100,
            position_y=200,
            width=120,
            height=60
        )
    
    def test_component_creation(self):
        """Test that components are created correctly"""
        self.assertEqual(self.component.name, 'test_component')
        self.assertEqual(self.component.component_type, 'model')
        self.assertTrue(self.component.is_active)
    
    def test_get_model_class(self):
        """Test that model class retrieval works"""
        model_class = self.component.get_model_class()
        self.assertIsNotNone(model_class)
        self.assertEqual(model_class.__name__, 'Technologies')
    
    def test_get_model_class_invalid(self):
        """Test handling of invalid model class names"""
        self.component.model_class_name = 'NonExistentModel'
        model_class = self.component.get_model_class()
        self.assertIsNone(model_class)
    
    def test_get_sample_data(self):
        """Test sample data retrieval"""
        # This assumes Technologies model has some test data
        column_names, sample_data = self.component.get_sample_data(limit=2)
        self.assertIsInstance(column_names, list)
        self.assertIsInstance(sample_data, list)
    
    def test_component_string_representation(self):
        """Test string representation"""
        expected = "Test Component (model)"
        self.assertEqual(str(self.component), expected)

class ComponentConnectionModelTests(TestCase):
    def setUp(self):
        self.component1 = SystemComponent.objects.create(
            name='component1',
            display_name='Component 1',
            component_type='model'
        )
        self.component2 = SystemComponent.objects.create(
            name='component2',
            display_name='Component 2',
            component_type='module'
        )
        self.connection = ComponentConnection.objects.create(
            from_component=self.component1,
            to_component=self.component2,
            connection_type='data_flow',
            description='Test connection'
        )
    
    def test_connection_creation(self):
        """Test that connections are created correctly"""
        self.assertEqual(self.connection.from_component, self.component1)
        self.assertEqual(self.connection.to_component, self.component2)
        self.assertTrue(self.connection.is_active)
    
    def test_connection_unique_constraint(self):
        """Test that duplicate connections are not allowed"""
        with self.assertRaises(Exception):
            ComponentConnection.objects.create(
                from_component=self.component1,
                to_component=self.component2,
                connection_type='process_flow'
            )
    
    def test_connection_string_representation(self):
        """Test string representation"""
        expected = "component1 -> component2"
        self.assertEqual(str(self.connection), expected)

class HomeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.component = SystemComponent.objects.create(
            name='test_component',
            display_name='Test Component',
            component_type='model',
            description='A test component',
            model_class_name='Technologies'
        )
    
    def test_home_view_get(self):
        """Test GET request to home view"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome to Siren Web!')
        self.assertIn('components', response.context)
    
    def test_component_details_ajax(self):
        """Test AJAX request for component details"""
        response = self.client.get(
            reverse('home'),
            {'component': 'test_component'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['component_name'], 'Test Component')
        self.assertIn('column_names', data)
        self.assertIn('sample_data', data)
    
    def test_component_details_not_found(self):
        """Test AJAX request for non-existent component"""
        response = self.client.get(
            reverse('home'),
            {'component': 'nonexistent'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'error')
        self.assertIn('message', data)

class ComponentConfigAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.component1 = SystemComponent.objects.create(
            name='component1',
            display_name='Component 1',
            component_type='model',
            position_x=100,
            position_y=200
        )
        self.component2 = SystemComponent.objects.create(
            name='component2',
            display_name='Component 2',
            component_type='module',
            position_x=300,
            position_y=400
        )
        ComponentConnection.objects.create(
            from_component=self.component1,
            to_component=self.component2,
            connection_type='data_flow'
        )
    
    def test_component_config_api(self):
        """Test component configuration API endpoint"""
        response = self.client.get(reverse('component_config'))
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('components', data)
        self.assertIn('connections', data)
        
        # Check component data structure
        components = data['components']
        self.assertEqual(len(components), 2)
        
        component = components[0]
        self.assertIn('name', component)
        self.assertIn('display_name', component)
        self.assertIn('type', component)
        self.assertIn('position', component)
        
        # Check connection data structure
        connections = data['connections']
        self.assertEqual(len(connections), 1)
        
        connection = connections[0]
        self.assertIn('from', connection)
        self.assertIn('to', connection)
        self.assertIn('type', connection)

class ComponentSystemIntegrationTests(TestCase):
    """Integration tests for the complete component system"""
    
    def setUp(self):
        self.client = Client()
        # Create a realistic component setup
        self.setup_realistic_components()
    
    def setup_realistic_components(self):
        """Set up a realistic component configuration"""
        # Database models
        self.weather = SystemComponent.objects.create(
            name='Weather',
            display_name='Weather Data',
            component_type='model',
            model_class_name='Weather',
            position_x=50,
            position_y=50
        )
        
        self.demand = SystemComponent.objects.create(
            name='Demand',
            display_name='Energy Demand',
            component_type='model',
            model_class_name='Demand',
            position_x=200,
            position_y=50
        )
        
        # Processing modules
        self.powermap = SystemComponent.objects.create(
            name='Powermap',
            display_name='Power Mapping',
            component_type='module',
            position_x=400,
            position_y=100
        )
        
        # Create connections
        ComponentConnection.objects.create(
            from_component=self.weather,
            to_component=self.powermap,
            connection_type='data_flow'
        )
        
        ComponentConnection.objects.create(
            from_component=self.demand,
            to_component=self.powermap,
            connection_type='data_flow'
        )
    
    def test_full_system_workflow(self):
        """Test the complete workflow from home page to component details"""
        # 1. Load home page
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        
        # 2. Get component configuration
        response = self.client.get(reverse('component_config'))
        self.assertEqual(response.status_code, 200)
        config_data = json.loads(response.content)
        
        # Verify all components are present
        component_names = [c['name'] for c in config_data['components']]
        self.assertIn('Weather', component_names)
        self.assertIn('Demand', component_names)
        self.assertIn('Powermap', component_names)
        
        # Verify connections are present
        self.assertEqual(len(config_data['connections']), 2)
        
        # 3. Get details for a specific component
        response = self.client.get(
            reverse('home'),
            {'component': 'Weather'}
        )
        self.assertEqual(response.status_code, 200)
        detail_data = json.loads(response.content)
        self.assertEqual(detail_data['component_name'], 'Weather Data')
    
    def test_component_admin_interface(self):
        """Test that admin interface works correctly"""
        # Create admin user
        admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='testpass123'
        )
        
        # Log in to admin
        self.client.login(username='admin', password='testpass123')
        
        # Test admin list view
        response = self.client.get('/admin/siren_web/systemcomponent/')
        self.assertEqual(response.status_code, 200)
        
        # Test adding a new component via admin
        response = self.client.post('/admin/siren_web/systemcomponent/add/', {
            'name': 'new_component',
            'display_name': 'New Component',
            'component_type': 'model',
            'description': 'A new test component',
            'position_x': 500,
            'position_y': 300,
            'width': 120,
            'height': 60,
            'is_active': True
        })
        
        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)
        
        # Verify component was created
        self.assertTrue(
            SystemComponent.objects.filter(name='new_component').exists()
        )

# Performance tests
class ComponentSystemPerformanceTests(TestCase):
    """Performance tests for the component system"""
    
    def test_large_number_of_components(self):
        """Test system performance with many components"""
        # Create 100 components
        components = []
        for i in range(100):
            components.append(SystemComponent(
                name=f'component_{i}',
                display_name=f'Component {i}',
                component_type='model' if i % 2 == 0 else 'module',
                position_x=i * 10,
                position_y=i * 5
            ))
        
        SystemComponent.objects.bulk_create(components)
        
        # Test that configuration API still performs well
        import time
        start_time = time.time()
        
        response = self.client.get(reverse('component_config'))
        
        end_time = time.time()
        response_time = end_time - start_time
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 1.0)  # Should respond within 1 second
        
        data = json.loads(response.content)
        self.assertEqual(len(data['components']), 100)