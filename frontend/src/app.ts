const API = 'http://localhost:8000';
const spacesOutput = document.querySelector<HTMLPreElement>('#spaces')!;
const quoteOutput = document.querySelector<HTMLPreElement>('#quote-output')!;
const analyticsOutput = document.querySelector<HTMLPreElement>('#analytics-output')!;
const spaceSelect = document.querySelector<HTMLSelectElement>('#space')!;

interface Space {
  id: number;
  name: string;
  capacity: number;
  base_hourly_rate_vnd: number;
  timezone_name: string;
}

function localInputToIso(value: string): string {
  const local = new Date(value);
  if (Number.isNaN(local.getTime())) throw new Error('Invalid date');
  return local.toISOString();
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  const data = await response.json();
  if (!response.ok) throw new Error(JSON.stringify(data));
  return data as T;
}

async function loadSpaces(): Promise<void> {
  const spaces = await request<Space[]>('/spaces');
  spacesOutput.textContent = JSON.stringify(spaces, null, 2);
  spaceSelect.replaceChildren(
    ...spaces.map((space) => {
      const option = document.createElement('option');
      option.value = String(space.id);
      option.textContent = `${space.name} - ${space.base_hourly_rate_vnd.toLocaleString('vi-VN')} VND/hour`;
      return option;
    }),
  );
}

document.querySelector<HTMLButtonElement>('#seed')!.addEventListener('click', async () => {
  try {
    await request('/spaces', {
      method: 'POST',
      body: JSON.stringify({
        name: 'Focus Room',
        capacity: 4,
        base_hourly_rate_vnd: 100000,
        timezone_name: 'Asia/Ho_Chi_Minh',
      }),
    });
  } catch (error) {
    // A duplicate demo space is harmless during local testing.
    console.info(error);
  }
  await loadSpaces();
});

document.querySelector<HTMLButtonElement>('#load')!.addEventListener('click', loadSpaces);

document.querySelector<HTMLFormElement>('#quote-form')!.addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const result = await request('/quotes', {
      method: 'POST',
      body: JSON.stringify({
        space_id: Number(spaceSelect.value),
        start_time: localInputToIso(document.querySelector<HTMLInputElement>('#start')!.value),
        end_time: localInputToIso(document.querySelector<HTMLInputElement>('#end')!.value),
      }),
    });
    quoteOutput.textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    quoteOutput.textContent = String(error);
  }
});

document.querySelector<HTMLFormElement>('#analytics-form')!.addEventListener('submit', async (event) => {
  event.preventDefault();
  const day = document.querySelector<HTMLInputElement>('#day')!.value;
  try {
    const query = new URLSearchParams({ day, timezone_name: 'Asia/Ho_Chi_Minh' });
    const result = await request(`/analytics/daily?${query.toString()}`);
    analyticsOutput.textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    analyticsOutput.textContent = String(error);
  }
});

loadSpaces().catch((error) => {
  spacesOutput.textContent = `API unavailable: ${String(error)}`;
});
