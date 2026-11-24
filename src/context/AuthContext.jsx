import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authApi, devicesApi } from '../services/api';
import { getOrCreateDeviceUUID, detectDeviceMetadata } from '../utils/deviceUtils';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const savedUser = localStorage.getItem('niyantra_user');
      return savedUser ? JSON.parse(savedUser) : null;
    } catch {
      return null;
    }
  });

  const [token, setToken] = useState(() => {
    try {
      return localStorage.getItem('niyantra_access_token') || null;
    } catch {
      return null;
    }
  });

  const [device, setDevice] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [authError, setAuthError] = useState(null);

  // Register current client hardware with backend
  const registerCurrentDevice = useCallback(async () => {
    try {
      const deviceUuid = getOrCreateDeviceUUID();
      const meta = detectDeviceMetadata();

      const registered = await devicesApi.register({
        device_uuid: deviceUuid,
        device_name: meta.deviceName,
        device_type: meta.deviceType,
        operating_system: meta.operatingSystem,
        client_version: meta.clientVersion,
      });
      setDevice(registered);
      return registered;
    } catch (e) {
      console.warn('Device registration deferred:', e.message);
      return null;
    }
  }, []);

  // Validate existing token on initial load
  useEffect(() => {
    let isMounted = true;

    async function checkAuth() {
      const storedToken = localStorage.getItem('niyantra_access_token');
      if (!storedToken) {
        if (isMounted) setIsLoading(false);
        return;
      }

      try {
        const userData = await authApi.getMe();
        if (isMounted) {
          setUser(userData);
          localStorage.setItem('niyantra_user', JSON.stringify(userData));
          // Register or ping active device
          registerCurrentDevice();
        }
      } catch (err) {
        console.warn('Stored session invalid or expired:', err.message);
        if (isMounted) {
          localStorage.removeItem('niyantra_access_token');
          localStorage.removeItem('niyantra_user');
          setUser(null);
          setToken(null);
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    checkAuth();
    return () => {
      isMounted = false;
    };
  }, [registerCurrentDevice]);

  // Login handler
  const login = useCallback(
    async (email, password) => {
      setAuthError(null);
      try {
        const res = await authApi.login(email, password);
        const { access_token, user: userData } = res;

        localStorage.setItem('niyantra_access_token', access_token);
        localStorage.setItem('niyantra_user', JSON.stringify(userData));

        setToken(access_token);
        setUser(userData);

        // Register client device upon authentication
        await registerCurrentDevice();
        return { success: true, user: userData };
      } catch (err) {
        const msg = err.data?.detail || err.message || 'Login failed';
        setAuthError(msg);
        return { success: false, error: msg };
      }
    },
    [registerCurrentDevice]
  );

  // Register handler
  const register = useCallback(
    async (name, email, password) => {
      setAuthError(null);
      try {
        const res = await authApi.register(name, email, password);
        const { access_token, user: userData } = res;

        localStorage.setItem('niyantra_access_token', access_token);
        localStorage.setItem('niyantra_user', JSON.stringify(userData));

        setToken(access_token);
        setUser(userData);

        await registerCurrentDevice();
        return { success: true, user: userData };
      } catch (err) {
        const msg = err.data?.detail || err.message || 'Registration failed';
        setAuthError(msg);
        return { success: false, error: msg };
      }
    },
    [registerCurrentDevice]
  );

  // Logout handler
  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem('niyantra_access_token');
      localStorage.removeItem('niyantra_user');
      setUser(null);
      setToken(null);
      setDevice(null);
    }
  }, []);

  const value = {
    user,
    token,
    device,
    isAuthenticated: Boolean(token && user),
    isLoading,
    authError,
    setAuthError,
    login,
    register,
    logout,
    registerCurrentDevice,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
