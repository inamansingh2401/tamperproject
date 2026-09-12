/**
 * SafeTrack Admin Console - Data API Layer
 * Connected directly to Python FastAPI Backend on https://safetrack-admin-c243.onrender.com
 */

const API_CONFIG = {
    BASE_URL: 'https://safetrack-admin-c243.onrender.com/api',
    USE_MOCK_DATA: false // Live FastAPI mode active
};

// ==========================================
// FALLBACK DEMO DATASTORE
// ==========================================

let mockVehicles = [
    { id: "TRK-MH-001", name: "Mumbai Central Warehouse", license_plate: "MH-04-JK-9021", driver: "Rajesh Kumar (DRV-882)", assigned_shipments: ["PRCL-2024-05-21-001", "PRCL-2024-05-21-007"], origin: "Mumbai Central Warehouse", destination: "Delhi Central Facility", current_hub: "Rewari Transit Hub, HR", status: "In Transit", last_update: "Just now" },
    { id: "TRK-WB-002", name: "Kolkata Hub", license_plate: "MH-12-PQ-4410", driver: "Amitabh Sen (DRV-419)", assigned_shipments: ["PRCL-2024-05-21-002"], origin: "Kolkata Hub", destination: "Bangalore Hub", current_hub: "Visakhapatnam Port Hub, AP", status: "In Transit", last_update: "15m ago" },
    { id: "TRK-TN-003", name: "Chennai Hub", license_plate: "DL-01-AX-3341", driver: "Srinivasan R. (DRV-305)", assigned_shipments: ["PRCL-2024-05-21-003"], origin: "Chennai Hub", destination: "Hyderabad Hub", current_hub: "Vijayawada Transit Yard, AP", status: "In Transit", last_update: "1h ago" },
    { id: "TRK-GJ-004", name: "Pune Warehouse", license_plate: "GJ-01-HG-8812", driver: "Vikram Patil (DRV-771)", assigned_shipments: ["PRCL-2024-05-21-004"], origin: "Pune Warehouse", destination: "Mumbai Hub", current_hub: "Panvel Checkpoint, MH", status: "Delayed", last_update: "25m ago" },
    { id: "TRK-RJ-005", name: "Ahmedabad Hub", license_plate: "UP-32-CD-5520", driver: "Karan Shah (DRV-612)", assigned_shipments: ["PRCL-2024-05-21-005"], origin: "Ahmedabad Hub", destination: "Delhi Facility", current_hub: "Jaipur Highway Hub, RJ", status: "In Transit", last_update: "10m ago" }
];

let mockShipments = [
    { id: "TRK-MH-001", title: "Cold-Chain Medicine & Vaccines", vehicle_id: "TRK-MH-001", sender: "Serum Bio-Tech Mumbai Hub", recipient: "Rahul Sharma", origin: "Mumbai Central Warehouse", destination: "Delhi Central Facility", current_hub: "Rewari Transit Hub, HR", status: "In Transit", seal_status: "Intact", health_level: "Optimal", latest_temperature: 4.2, latest_light: 0.0, latest_humidity: 45.0, latest_shock: "Normal (0.2g)", last_update: "Just now" },
    { id: "PRCL-2024-05-21-007", title: "Insulin Injection Pens & Cold Syringes", vehicle_id: "TRK-MH-001", sender: "Serum Bio-Tech Mumbai Hub", recipient: "Priya Sharma", origin: "Mumbai Central Warehouse", destination: "Delhi Central Facility", current_hub: "Rewari Transit Hub, HR", status: "In Transit", seal_status: "Intact", health_level: "Optimal", latest_temperature: 4.0, latest_light: 0.0, latest_humidity: 44.0, latest_shock: "Normal (0.1g)", last_update: "Just now" },
    { id: "TRK-WB-002", title: "Oncology Biologic Cancer Therapy", vehicle_id: "TRK-WB-002", sender: "Kolkata Medical Depot", recipient: "Dr. A. K. Roy", origin: "Kolkata Hub", destination: "Bangalore Hub", current_hub: "Visakhapatnam Port Hub, AP", status: "In Transit", seal_status: "Intact", health_level: "Degraded", latest_temperature: 5.1, latest_light: 12.0, latest_humidity: 52.0, latest_shock: "Minor Bump (0.8g)", last_update: "15m ago" },
    { id: "TRK-TN-003", title: "mRNA Booster Doses & Cell Cultures", vehicle_id: "TRK-TN-003", sender: "Chennai Vaccine Research", recipient: "Hyderabad Hospital", origin: "Chennai Hub", destination: "Hyderabad Hub", current_hub: "Vijayawada Transit Yard, AP", status: "In Transit", seal_status: "Intact", health_level: "Optimal", latest_temperature: 3.8, latest_light: 0.0, latest_humidity: 38.0, latest_shock: "Normal (0.1g)", last_update: "1h ago" },
    { id: "TRK-GJ-004", title: "Monoclonal Antibodies & Immunotherapy", vehicle_id: "TRK-GJ-004", sender: "Pune Bio-Tech Park", recipient: "Mumbai Air Cargo Terminal", origin: "Pune Warehouse", destination: "Mumbai Hub", current_hub: "Panvel Checkpoint, MH", status: "Compromised", seal_status: "BREACHED", health_level: "Compromised", latest_temperature: 16.5, latest_light: 850.0, latest_humidity: 68.0, latest_shock: "High Impact (3.4g)", last_update: "25m ago" },
    { id: "TRK-RJ-005", title: "Ophthalmic Sterile Solutions & Drops", vehicle_id: "TRK-RJ-005", sender: "Ahmedabad Formulations", recipient: "Delhi Eye Institute", origin: "Ahmedabad Hub", destination: "Delhi Facility", current_hub: "Jaipur Highway Hub, RJ", status: "In Transit", seal_status: "Intact", health_level: "Optimal", latest_temperature: 4.0, latest_light: 0.0, latest_humidity: 40.0, latest_shock: "Normal (0.2g)", last_update: "10m ago" }
];

let mockAlerts = [
    { id: "ALT-2024-001", severity: "Critical", alert_type: "Seal Breach / Light Exposure", shipment_id: "TRK-GJ-004", vehicle_id: "TRK-GJ-004", location: "Panvel Checkpoint, MH", timestamp: "Just now", message: "CRITICAL TAMPER: Container opened (850 LUX; threshold 800 LUX) at Panvel Checkpoint!", status: "Active" },
    { id: "ALT-2024-002", severity: "Critical", alert_type: "Severe Impact Shock", shipment_id: "TRK-GJ-004", vehicle_id: "TRK-GJ-004", location: "Panvel Checkpoint, MH", timestamp: "5m ago", message: "CRITICAL EXCURSION: Severe impact shock (3.4g) detected on MPU6050 sensor!", status: "Active" },
    { id: "ALT-2024-003", severity: "Warning", alert_type: "Temperature Warning", shipment_id: "TRK-WB-002", vehicle_id: "TRK-WB-002", location: "Visakhapatnam Port Hub, AP", timestamp: "15m ago", message: "WARNING: Stress parameter (Temp: 5.1°C slightly above target threshold).", status: "Active" }
];

let mockUsers = [
    { id: 1, name: "Admin Super", email: "admin@safetrack.com", role: "Admin", assigned_vehicles: ["All Vehicles"], status: "Active", last_login: "Just now" },
    { id: 2, name: "Rahul Sharma", email: "rahul.sharma@safetrack.com", role: "User", assigned_vehicles: ["PRCL-2024-05-21-001", "PRCL-2024-05-21-007"], status: "Active", last_login: "10m ago" },
    { id: 3, name: "Priya Sharma", email: "priya.sharma@safetrack.com", role: "User", assigned_vehicles: ["PRCL-2024-05-21-002", "PRCL-2024-05-21-008"], status: "Active", last_login: "5m ago" },
    { id: 4, name: "Arjun Reddy", email: "arjun.reddy@safetrack.com", role: "User", assigned_vehicles: ["PRCL-2024-05-21-003", "PRCL-2024-05-21-009"], status: "Active", last_login: "12m ago" }
];

// ==========================================
// AUTHENTICATED FASTAPI LIVE BACKEND CONNECTIVITY
// ==========================================

function connectionStatus(message, failed) {
    let bar = document.getElementById('tracksure-connection');
    if (!bar) {
        bar = document.createElement('div'); bar.id = 'tracksure-connection';
        bar.setAttribute('role','status');
        bar.style.cssText = 'padding:10px 14px;margin:12px 16px 0;border-radius:8px;font:13px system-ui;overflow-wrap:anywhere';
        const header = document.querySelector('main > header');
        if (header) header.after(bar); else document.body.appendChild(bar);
    }
    bar.style.background = failed ? '#fff1f2' : '#f0fdf4';
    bar.style.color = failed ? '#9f1239' : '#166534';
    bar.textContent = message;
}

async function authFetch(url, options = {}) {
    const token = sessionStorage.getItem('safetrack_access_token');
    const headers = new Headers(options.headers || {});
    if (token) headers.set('Authorization', `Bearer ${token}`);
    try {
        const response = await fetchWithTimeout(url, {...options, headers, cache:'no-store'});
        if (!response.ok) {
            if (response.status === 401) {
                sessionStorage.removeItem('safetrack_access_token');
                if (!location.pathname.endsWith('login.html')) location.replace('login.html');
            }
            let detail = `API returned HTTP ${response.status}`;
            try { const body = await response.clone().json(); if (typeof body.detail === 'string') detail = body.detail; } catch (_) {}
            throw new Error(detail);
        }
        connectionStatus('Cloud connected · Open Live sensors for reading freshness', false);
        return response;
    } catch (error) {
        connectionStatus('Cloud unavailable: displayed values may be stale. ' + error.message, true);
        throw error;
    }
}

const SafeTrackAPI = {
    async getVehicles() {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/vehicles`);
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, loading mock vehicles", e);
            }
        }
        return [...mockVehicles];
    },

    async getVehicleById(vehicleId) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/vehicles/${vehicleId}`);
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, loading mock vehicle", e);
            }
        }
        return mockVehicles.find(v => v.id === vehicleId) || mockVehicles[0];
    },

    async createVehicle(vehicleData) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/vehicles`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(vehicleData)
                });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, saving locally", e);
            }
        }
        const newVehicle = {
            id: vehicleData.id || `TRK-AUTO-${String(mockVehicles.length + 1).padStart(3, "0")}`,
            name: vehicleData.name || "Reefer Van",
            license_plate: vehicleData.license_plate || "MH-04-JK-9021",
            driver: vehicleData.driver || "Unassigned Operator",
            assigned_shipments: vehicleData.assigned_shipments || [],
            origin: vehicleData.origin || "Mumbai Warehouse",
            destination: vehicleData.destination || "Delhi Facility",
            current_hub: vehicleData.origin || "Mumbai Warehouse",
            status: vehicleData.status || "In Transit",
            last_update: "Just now"
        };
        mockVehicles.unshift(newVehicle);
        return newVehicle;
    },

    async updateVehicle(vehicleId, updateData) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/vehicles/${vehicleId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updateData)
                });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend error updating vehicle", e);
            }
        }
        const index = mockVehicles.findIndex(v => v.id === vehicleId);
        if (index !== -1) {
            mockVehicles[index] = { ...mockVehicles[index], ...updateData };
            return mockVehicles[index];
        }
        return updateData;
    },

    async deleteVehicle(vehicleId) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/vehicles/${vehicleId}`, { method: 'DELETE' });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend error deleting vehicle", e);
            }
        }
        mockVehicles = mockVehicles.filter(v => v.id !== vehicleId);
        return { success: true };
    },

    async assignShipmentToVehicle(vehicleId, shipmentCode) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/vehicles/${vehicleId}/assign-shipment`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ shipment_code: shipmentCode })
                });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend error assigning shipment", e);
            }
        }
        const v = mockVehicles.find(item => item.id === vehicleId);
        if (v && !v.assigned_shipments.includes(shipmentCode)) {
            v.assigned_shipments.push(shipmentCode);
        }
        return { success: true };
    },

    async getShipments() {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/shipments`);
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, loading mock shipments", e);
            }
        }
        return [...mockShipments];
    },

    async getShipmentByCode(code) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/shipments/${code}`);
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, loading mock shipment code", e);
            }
        }
        const shipment = mockShipments.find(s => s.id === code) || mockShipments[0];
        return {
            shipment,
            alerts: mockAlerts.filter(a => a.shipment_id === code),
            latest_telemetry: {
                temperature: shipment.latest_temperature,
                light_lux: shipment.latest_light,
                humidity: shipment.latest_humidity,
                accel_g: 1.0,
                previous_hash: "0000000000000000000000000000000000000000000000000000000000000000",
                record_hash: "GENESIS_HASH_PRCL_VERIFIED_PROOF"
            }
        };
    },

    async getLiveTelemetry(shipmentId) {
        if (!shipmentId) throw new Error('Choose a shipment');
        const result = await this.getShipmentByCode(shipmentId);
        return result.latest_telemetry;
    },

    async createShipment(shipmentData) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/shipments`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(shipmentData)
                });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, saving shipment locally", e);
            }
        }
        const newShipment = {
            id: shipmentData.id,
            title: shipmentData.title,
            vehicle_id: shipmentData.vehicle_id,
            sender: shipmentData.sender || "Serum Bio-Tech Hub",
            recipient: shipmentData.recipient_name || "Rahul Sharma",
            origin: shipmentData.origin,
            destination: shipmentData.destination,
            current_hub: shipmentData.origin,
            status: shipmentData.status || "In Transit",
            seal_status: "Intact",
            health_level: "Optimal",
            latest_temperature: 4.2,
            latest_light: 0.0,
            latest_humidity: 45.0,
            latest_shock: "Normal (0.2g)",
            last_update: "Just now"
        };
        mockShipments.unshift(newShipment);
        return newShipment;
    },

    async updateShipment(shipmentId, updateData) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/shipments/${shipmentId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(updateData)
                });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend error updating shipment", e);
            }
        }
        const index = mockShipments.findIndex(s => s.id === shipmentId);
        if (index !== -1) {
            mockShipments[index] = { ...mockShipments[index], ...updateData };
            return mockShipments[index];
        }
        return updateData;
    },

    async deleteShipment(shipmentId) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/shipments/${shipmentId}`, { method: 'DELETE' });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend error deleting shipment", e);
            }
        }
        mockShipments = mockShipments.filter(s => s.id !== shipmentId);
        return { success: true };
    },

    async removeShipmentFromVehicle(shipmentId, vehicleId) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/vehicles/${vehicleId}/remove-shipment`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ shipment_code: shipmentId })
                });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend error removing shipment", e);
            }
        }
        const vehicle = mockVehicles.find(v => v.id === vehicleId);
        if (vehicle) {
            vehicle.assigned_shipments = vehicle.assigned_shipments.filter(id => id !== shipmentId);
        }
        return { success: true };
    },

    async getAlerts() {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/alerts`);
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, loading mock alerts", e);
            }
        }
        return [...mockAlerts];
    },

    async resolveAlert(alertId) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/alerts/${alertId}/resolve`, { method: 'PUT' });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, resolving locally", e);
            }
        }
        const alert = mockAlerts.find(a => a.id === alertId);
        if (alert) {
            alert.status = "Resolved";
            alert.severity = "Resolved";
        }
        return { status: "Resolved" };
    },

    async resolveAllAlerts() {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/alerts/resolve-all`, { method: 'PUT' });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, resolving all alerts locally", e);
            }
        }
        mockAlerts.forEach(a => {
            a.status = "Resolved";
            a.severity = "Resolved";
        });
        return { status: "Resolved" };
    },

    async getUsers() {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/users`);
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, loading mock users", e);
            }
        }
        return [...mockUsers];
    },

    async createUser(userData) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/users`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(userData)
                });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, creating user locally", e);
            }
        }
        const newUser = {
            id: mockUsers.length + 1,
            name: userData.name,
            email: userData.email,
            role: userData.role || "Operator",
            assigned_vehicles: userData.assigned_vehicles || ["PRCL-2024-05-21-001"],
            status: "Active",
            last_login: "Never"
        };
        mockUsers.push(newUser);
        return newUser;
    },

    async updateUser(userId, userData) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/users/${userId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(userData)
                });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend error updating user", e);
            }
        }
        const user = mockUsers.find(u => u.id === userId);
        if (user) {
            Object.assign(user, userData);
            return user;
        }
        return userData;
    },

    async toggleUserStatus(userId) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/users/${userId}/toggle-status`, { method: 'PUT' });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, toggling status locally", e);
            }
        }
        const user = mockUsers.find(u => u.id === userId);
        if (user) {
            user.status = user.status === "Active" ? "Disabled" : "Active";
            return user;
        }
        return { status: "Active" };
    },

    async getSettings() {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/settings`);
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, using default settings", e);
            }
        }
        return {
            system_name: "SafeTrack Logistics & Security Control Center",
            default_temp_threshold: 8.0,
            default_alert_threshold: 800.0,
            language: "English",
            alert_notifications: true,
            shipment_updates: true,
            email_notifications: true,
            session_timeout: 30
        };
    },

    async updateSettings(category, data) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/settings`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend error saving settings", e);
            }
        }
        return { success: true };
    },

    async changePassword(currentPassword, newPassword) {
        if (!API_CONFIG.USE_MOCK_DATA) {
            const res = await authFetch(`${API_CONFIG.BASE_URL}/settings/change-password`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to update password");
            return data;
        }
        return { success: true };
    },

    async getReportsSummary() {
        if (!API_CONFIG.USE_MOCK_DATA) {
            try {
                const res = await authFetch(`${API_CONFIG.BASE_URL}/reports/summary`);
                if (res.ok) return await res.json();
            } catch (e) {
                if (!API_CONFIG.USE_MOCK_DATA) throw e;
                console.warn("Backend offline, getting summary locally", e);
            }
        }
        return {
            total_shipments: mockShipments.length,
            total_vehicles: mockVehicles.length,
            total_events: 1280,
            total_alerts: mockAlerts.length,
            active_alerts_count: mockAlerts.filter(a => a.status === "Active").length,
            compliance_percentage: 96.8,
            temp_alerts: 1,
            tamper_alerts: 1,
            shock_alerts: 1
        };
    }
};

window.SafeTrackAPI = SafeTrackAPI;
