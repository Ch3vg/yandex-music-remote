import { useState } from 'react';
import { send, sessionToken } from '../api/ws';
import { useRole } from '../store/role';
import './RoleUnlock.css';

export function RoleUnlock() {
  const [pin, setPin] = useState('');
  const admin = useRole() === 'admin';
  return (
    <div className="role-unlock">
      <div className="role-unlock-title">{admin ? 'Администратор' : 'Гость'}</div>
      {admin ? (
        <button
          type="button"
          className="role-unlock-btn"
          onClick={() => {
            const token = sessionToken();
            send(token ? { command: 'lock', token } : { command: 'lock' });
          }}
        >
          Выйти
        </button>
      ) : (
        <form
          className="role-unlock-form"
          onSubmit={(event) => {
            event.preventDefault();
            const value = pin.trim();
            if (!value) return;
            send({ command: 'unlock', pin: value });
            setPin('');
          }}
        >
          <input
            type="password"
            inputMode="numeric"
            autoComplete="off"
            placeholder="PIN администратора"
            value={pin}
            onChange={(event) => setPin(event.target.value)}
          />
          <button type="submit" className="role-unlock-btn">
            Войти
          </button>
        </form>
      )}
    </div>
  );
}
