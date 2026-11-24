/**
 * Device Identity & Hardware Profiling Utility
 * Ensures stable device UUID preservation across application restarts
 * without triggering synchronization.
 */

export function getOrCreateDeviceUUID() {
  if (typeof window === 'undefined' || !window.localStorage) {
    return '00000000-0000-0000-0000-000000000001';
  }

  const STORAGE_KEY = 'niyantra_device_uuid';
  let deviceUuid = window.localStorage.getItem(STORAGE_KEY);
  if (!deviceUuid) {
    // Generate UUIDv4
    deviceUuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === 'x' ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
    window.localStorage.setItem(STORAGE_KEY, deviceUuid);
  }
  return deviceUuid;
}

export function detectDeviceMetadata() {
  if (typeof window === 'undefined') {
    return {
      deviceName: 'Desktop Client',
      deviceType: 'Desktop',
      operatingSystem: 'Unknown',
      clientVersion: '2.0.0',
    };
  }

  const ua = navigator.userAgent || '';
  let os = 'Unknown OS';
  if (/windows phone/i.test(ua)) os = 'Windows Phone';
  else if (/win/i.test(ua)) os = 'Windows';
  else if (/android/i.test(ua)) os = 'Android';
  else if (/ipad|iphone|ipod/i.test(ua)) os = 'iOS';
  else if (/mac/i.test(ua)) os = 'macOS';
  else if (/linux/i.test(ua)) os = 'Linux';

  let deviceType = 'Laptop';
  if (/tablet|ipad/i.test(ua)) {
    deviceType = 'Tablet';
  } else if (/mobile|iphone|ipod|android/i.test(ua)) {
    deviceType = 'Mobile';
  } else if (os === 'Windows' || os === 'macOS' || os === 'Linux') {
    deviceType = 'Laptop';
  }

  // Detect browser name for friendly device name
  let browser = 'Browser';
  if (ua.includes('Firefox')) browser = 'Firefox';
  else if (ua.includes('Edg')) browser = 'Edge';
  else if (ua.includes('Chrome')) browser = 'Chrome';
  else if (ua.includes('Safari')) browser = 'Safari';

  const deviceName = `${browser} on ${os}`;

  return {
    deviceName,
    deviceType,
    operatingSystem: os,
    clientVersion: '2.0.0',
  };
}
