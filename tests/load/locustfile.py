"""
Locust load testing for MLOps API.

Run with:
    locust -f tests/load/locustfile.py --host=http://localhost:30800
    
Or headless:
    locust -f tests/load/locustfile.py --host=http://localhost:30800 --headless -u 100 -r 10 -t 5m
"""
from locust import HttpUser, task, between, events
import random
import json
import logging

# Sample states for testing
STATES = [
    "California", "Texas", "Florida", "New York", "Pennsylvania",
    "Illinois", "Ohio", "Georgia", "North Carolina", "Michigan",
    "New Jersey", "Virginia", "Washington", "Arizona", "Massachusetts",
    "Tennessee", "Indiana", "Missouri", "Maryland", "Wisconsin"
]

# Sample property configurations
PROPERTY_CONFIGS = [
    {"bed": 2, "bath": 1, "acre_lot": 0.1, "house_size": 1000, "status": "for_sale"},
    {"bed": 3, "bath": 2, "acre_lot": 0.25, "house_size": 1500, "status": "for_sale"},
    {"bed": 3, "bath": 2, "acre_lot": 0.25, "house_size": 1800, "status": "sold"},
    {"bed": 4, "bath": 2.5, "acre_lot": 0.5, "house_size": 2200, "status": "for_sale"},
    {"bed": 4, "bath": 3, "acre_lot": 0.75, "house_size": 2800, "status": "for_sale"},
    {"bed": 5, "bath": 3, "acre_lot": 1.0, "house_size": 3500, "status": "sold"},
    {"bed": 5, "bath": 4, "acre_lot": 2.0, "house_size": 4500, "status": "for_sale"},
    {"bed": 6, "bath": 4, "acre_lot": 5.0, "house_size": 6000, "status": "for_sale"},
]


class MLOpsAPIUser(HttpUser):
    """
    Simulates a user interacting with the MLOps prediction API.
    
    Task weights:
    - predict: 70% (most common operation)
    - explain: 15% (SHAP explanations)
    - health: 10% (health checks)
    - model_info: 5% (checking model status)
    """
    wait_time = between(0.5, 2)  # Wait 0.5-2 seconds between requests
    
    def on_start(self):
        """Called when a user starts."""
        # Verify API is healthy before starting tests
        response = self.client.get("/health")
        if response.status_code != 200:
            logging.warning(f"API health check failed: {response.status_code}")
    
    @task(70)
    def predict_random(self):
        """Make a prediction with random property data."""
        config = random.choice(PROPERTY_CONFIGS).copy()
        config["state"] = random.choice(STATES)
        
        # Add some randomness to numeric values
        config["bed"] = config["bed"] + random.randint(-1, 1)
        config["bed"] = max(1, config["bed"])  # Ensure positive
        config["bath"] = config["bath"] + random.uniform(-0.5, 0.5)
        config["bath"] = max(0.5, config["bath"])
        config["house_size"] = int(config["house_size"] * random.uniform(0.8, 1.2))
        config["acre_lot"] = config["acre_lot"] * random.uniform(0.5, 1.5)
        
        with self.client.post(
            "/predict",
            json=config,
            catch_response=True,
            name="/predict"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "price" not in data:
                    response.failure("Response missing 'price' field")
                elif data["price"] <= 0:
                    response.failure(f"Invalid price: {data['price']}")
            elif response.status_code == 503:
                response.failure("Model not loaded")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(15)
    def explain_prediction(self):
        """Request SHAP explanation for a prediction."""
        config = random.choice(PROPERTY_CONFIGS).copy()
        config["state"] = random.choice(STATES)
        
        with self.client.post(
            "/explain",
            json=config,
            catch_response=True,
            name="/explain"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "shap_values" not in data:
                    response.failure("Response missing 'shap_values'")
                if "base_value" not in data:
                    response.failure("Response missing 'base_value'")
            elif response.status_code == 503:
                # Explainer might not be loaded - mark as expected
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(10)
    def health_check(self):
        """Check API health."""
        with self.client.get(
            "/health",
            catch_response=True,
            name="/health"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") not in ["healthy", "degraded"]:
                    response.failure(f"Unexpected status: {data.get('status')}")
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    @task(5)
    def get_model_info(self):
        """Get model information."""
        with self.client.get(
            "/model",
            catch_response=True,
            name="/model"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "model_version" not in data:
                    response.failure("Response missing 'model_version'")
            else:
                response.failure(f"Model info failed: {response.status_code}")


class BatchPredictionUser(HttpUser):
    """
    Simulates batch prediction requests.
    Lower frequency, higher payload.
    """
    wait_time = between(5, 15)  # Longer wait between batch requests
    weight = 1  # Lower weight than regular users
    
    @task
    def batch_predict(self):
        """Make batch predictions."""
        # Generate 10-50 properties
        batch_size = random.randint(10, 50)
        properties = []
        
        for _ in range(batch_size):
            config = random.choice(PROPERTY_CONFIGS).copy()
            config["state"] = random.choice(STATES)
            properties.append(config)
        
        with self.client.post(
            "/batch_predict",
            json=properties,
            catch_response=True,
            name="/batch_predict"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "predictions" not in data:
                    response.failure("Response missing 'predictions'")
                elif len(data["predictions"]) != batch_size:
                    response.failure(f"Expected {batch_size} predictions, got {len(data['predictions'])}")
            elif response.status_code == 503:
                response.failure("Model not loaded")
            else:
                response.failure(f"Batch predict failed: {response.status_code}")


# Custom event handlers for logging
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, exception, **kwargs):
    """Log slow requests."""
    if response_time > 2000:  # > 2 seconds
        logging.warning(f"Slow request: {name} took {response_time}ms")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    logging.info("Load test starting...")
    logging.info(f"Target host: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    logging.info("Load test completed")
    
    # Print summary statistics
    stats = environment.stats
    logging.info(f"Total requests: {stats.total.num_requests}")
    logging.info(f"Total failures: {stats.total.num_failures}")
    if stats.total.num_requests > 0:
        logging.info(f"Failure rate: {stats.total.num_failures / stats.total.num_requests * 100:.2f}%")
        logging.info(f"Average response time: {stats.total.avg_response_time:.2f}ms")
        logging.info(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")

