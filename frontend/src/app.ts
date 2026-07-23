const API = (
  import.meta.env.VITE_API_URL
  ?? (['localhost', '127.0.0.1'].includes(window.location.hostname)
    ? 'http://localhost:8000'
    : '')
).replace(/\/$/, '');

interface Space {
  id: number;
  name: string;
  capacity: number;
  base_hourly_rate_vnd: number;
  timezone_name: string;
  active: boolean;
}

interface Quote {
  space_id: number;
  hours: number;
  occupancy_ratio: number;
  multiplier: number;
  total_price_vnd: number;
  currency: string;
}

interface Booking {
  id: number;
  space_id: number;
  customer_name: string;
  start_time: string;
  end_time: string;
  total_price_vnd: number;
  status: string;
}

interface Analytics {
  day: string;
  timezone_name: string;
  confirmed_bookings: number;
  booked_hours: number;
  revenue_vnd: number;
}

interface QuotePayload {
  space_id: number;
  start_time: string;
  end_time: string;
}

function element<T extends HTMLElement>(selector: string): T {
  const found = document.querySelector<T>(selector);
  if (!found) throw new Error(`Missing required element: ${selector}`);
  return found;
}

const spaceSelect = element<HTMLSelectElement>('#space');
const startInput = element<HTMLInputElement>('#start');
const endInput = element<HTMLInputElement>('#end');
const customerInput = element<HTMLInputElement>('#customer-name');
const dayInput = element<HTMLInputElement>('#day');
const quoteButton = element<HTMLButtonElement>('#quote-button');
const confirmButton = element<HTMLButtonElement>('#confirm-button');
const analyticsButton = element<HTMLButtonElement>('#analytics-button');
const apiStatus = element<HTMLDivElement>('#api-status');
const apiStatusText = element<HTMLSpanElement>('#api-status-text');
const toast = element<HTMLDivElement>('#toast');

let spaces: Space[] = [];
let bookings: Booking[] = [];
let currentQuote: Quote | null = null;
let currentQuotePayload: QuotePayload | null = null;
let toastTimer: number | undefined;

function formatVnd(value: number): string {
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDateTime(value: string): string {
  // Booking timestamps are stored as naive UTC in the API model. Append Z when
  // the serialized value has no offset so browsers do not reinterpret UTC as local.
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  return new Intl.DateTimeFormat('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(normalized));
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  })[character] ?? character);
}

function localDateTimeValue(value: Date): string {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

function localDateValue(value: Date): string {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 10);
}

function localInputToIso(value: string): string {
  const local = new Date(value);
  if (Number.isNaN(local.getTime())) throw new Error('Enter a valid date and time.');
  return local.toISOString();
}

function friendlyError(data: unknown): string {
  let message = 'Something went wrong. Please try again.';

  if (typeof data === 'string') {
    message = data;
  } else if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === 'string') {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail
        .map((item) => {
          if (item && typeof item === 'object' && 'msg' in item) {
            return String((item as { msg: unknown }).msg).replace(/^Value error,\s*/i, '');
          }
          return String(item);
        })
        .join(' ');
    }
  }

  const replacements: Record<string, string> = {
    'bookings may not exceed 12 hours': 'Booking duration cannot exceed 12 hours.',
    'end_time must be after start_time': 'End time must be after start time.',
    'space is already booked during this interval': 'This workspace is already booked for that time.',
    'active space not found': 'That workspace is no longer available.',
    'space name already exists': 'The demo space already exists.',
    'booking not found': 'That booking could not be found.',
  };

  return replacements[message.toLowerCase()] ?? message;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new Error('The API is unavailable. Check the deployment and try again.');
  }

  const contentType = response.headers.get('content-type') ?? '';
  const data: unknown = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) throw new Error(friendlyError(data));
  return data as T;
}

function setApiStatus(connected: boolean): void {
  apiStatus.classList.toggle('connected', connected);
  apiStatus.classList.toggle('disconnected', !connected);
  apiStatusText.textContent = connected ? 'API connected' : 'API unavailable';
}

function setButtonBusy(button: HTMLButtonElement, busy: boolean, label: string): void {
  button.disabled = busy;
  if (busy) {
    button.dataset.idleLabel = button.textContent ?? label;
    button.textContent = label;
  } else if (button.dataset.idleLabel) {
    button.textContent = button.dataset.idleLabel;
    delete button.dataset.idleLabel;
  }
}

function showToast(message: string, kind: 'success' | 'error' = 'success'): void {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.className = `toast ${kind} visible`;
  toastTimer = window.setTimeout(() => {
    toast.classList.remove('visible');
  }, 3600);
}

function showMessage(targetSelector: string, message: string, kind: 'success' | 'error'): void {
  const target = element<HTMLDivElement>(targetSelector);
  target.className = kind === 'success' ? 'success-box' : 'error-box';
  target.textContent = message;
}

function clearMessage(targetSelector: string): void {
  const target = element<HTMLDivElement>(targetSelector);
  target.className = '';
  target.textContent = '';
}

function renderSpaces(): void {
  const list = element<HTMLDivElement>('#space-list');
  element<HTMLElement>('#metric-spaces').textContent = String(spaces.length);

  if (spaces.length === 0) {
    list.innerHTML = '<div class="empty-state">No active workspaces yet. Create the demo space to begin.</div>';
    spaceSelect.innerHTML = '<option value="">No spaces available</option>';
    quoteButton.disabled = true;
    confirmButton.disabled = true;
    return;
  }

  quoteButton.disabled = false;
  const selected = spaceSelect.value;
  spaceSelect.replaceChildren(...spaces.map((space) => {
    const option = document.createElement('option');
    option.value = String(space.id);
    option.textContent = `${space.name} · ${formatVnd(space.base_hourly_rate_vnd)}/hour`;
    return option;
  }));
  if (spaces.some((space) => String(space.id) === selected)) spaceSelect.value = selected;

  list.innerHTML = spaces.map((space) => `
    <article class="room-card">
      <div>
        <p class="room-name">${escapeHtml(space.name)}</p>
        <p class="room-meta">Capacity ${space.capacity} · ${escapeHtml(space.timezone_name)}</p>
      </div>
      <div class="rate">${formatVnd(space.base_hourly_rate_vnd)}/h</div>
    </article>
  `).join('');
}

function renderBookings(): void {
  const list = element<HTMLDivElement>('#booking-list');
  const confirmed = bookings.filter((booking) => booking.status === 'confirmed');
  element<HTMLElement>('#metric-bookings').textContent = String(confirmed.length);

  if (bookings.length === 0) {
    list.innerHTML = '<div class="empty-state">No bookings yet. Calculate a quote and confirm it above.</div>';
    return;
  }

  const byId = new Map(spaces.map((space) => [space.id, space]));
  list.innerHTML = bookings
    .slice()
    .sort((a, b) => new Date(b.start_time).getTime() - new Date(a.start_time).getTime())
    .map((booking) => {
      const space = byId.get(booking.space_id);
      const canCancel = booking.status === 'confirmed';
      return `
        <article class="booking-card">
          <div>
            <div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px">
              <p class="booking-name">${escapeHtml(space?.name ?? `Space #${booking.space_id}`)}</p>
              <span class="status-badge status-${escapeHtml(booking.status)}">${escapeHtml(booking.status)}</span>
            </div>
            <p class="booking-meta">
              ${escapeHtml(booking.customer_name)}<br />
              ${formatDateTime(booking.start_time)} to ${formatDateTime(booking.end_time)}<br />
              ${formatVnd(booking.total_price_vnd)}
            </p>
          </div>
          ${canCancel ? `<button class="button button-danger button-small" type="button" data-cancel-booking="${booking.id}">Cancel</button>` : ''}
        </article>
      `;
    })
    .join('');
}

function renderQuote(quote: Quote): void {
  const card = element<HTMLDivElement>('#quote-card');
  card.hidden = false;
  element<HTMLElement>('#quote-price').textContent = formatVnd(quote.total_price_vnd);
  element<HTMLElement>('#quote-hours').textContent = `${quote.hours} ${quote.hours === 1 ? 'hour' : 'hours'}`;
  element<HTMLElement>('#quote-occupancy').textContent = `${Math.round(quote.occupancy_ratio * 100)}%`;
  element<HTMLElement>('#quote-multiplier').textContent = `${quote.multiplier.toFixed(2)}×`;
}

function clearQuote(): void {
  currentQuote = null;
  currentQuotePayload = null;
  confirmButton.disabled = true;
  element<HTMLDivElement>('#quote-card').hidden = true;
  clearMessage('#booking-message');
}

function renderAnalytics(analytics: Analytics): void {
  element<HTMLElement>('#analytics-bookings').textContent = String(analytics.confirmed_bookings);
  element<HTMLElement>('#analytics-hours').textContent = `${analytics.booked_hours.toFixed(2)} h`;
  element<HTMLElement>('#analytics-revenue').textContent = formatVnd(analytics.revenue_vnd);
  element<HTMLElement>('#metric-revenue').textContent = formatVnd(analytics.revenue_vnd);
}

function quotePayloadFromForm(): QuotePayload {
  if (!spaceSelect.value) throw new Error('Choose a workspace first.');
  const start = new Date(startInput.value);
  const end = new Date(endInput.value);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    throw new Error('Enter a valid start and end time.');
  }
  if (end <= start) throw new Error('End time must be after start time.');
  if (end.getTime() - start.getTime() > 12 * 60 * 60 * 1000) {
    throw new Error('Booking duration cannot exceed 12 hours.');
  }

  return {
    space_id: Number(spaceSelect.value),
    start_time: localInputToIso(startInput.value),
    end_time: localInputToIso(endInput.value),
  };
}

async function loadSpaces(): Promise<void> {
  spaces = await request<Space[]>('/spaces');
  renderSpaces();
}

async function loadBookings(): Promise<void> {
  bookings = await request<Booking[]>('/bookings');
  renderBookings();
}

async function loadAnalytics(): Promise<void> {
  clearMessage('#analytics-message');
  const query = new URLSearchParams({
    day: dayInput.value,
    timezone_name: 'Asia/Ho_Chi_Minh',
  });
  const analytics = await request<Analytics>(`/analytics/daily?${query.toString()}`);
  renderAnalytics(analytics);
}

function setDefaultDates(): void {
  const start = new Date();
  start.setSeconds(0, 0);
  const minuteRemainder = start.getMinutes() % 30;
  start.setMinutes(start.getMinutes() + (minuteRemainder === 0 ? 30 : 30 - minuteRemainder));
  const end = new Date(start.getTime() + 60 * 60 * 1000);

  startInput.value = localDateTimeValue(start);
  endInput.value = localDateTimeValue(end);
  dayInput.value = localDateValue(start);
}

for (const input of [spaceSelect, startInput, endInput]) {
  input.addEventListener('change', clearQuote);
  input.addEventListener('input', clearQuote);
}

{
  element<HTMLButtonElement>('#seed').addEventListener('click', async (event) => {
    const button = event.currentTarget as HTMLButtonElement;
    setButtonBusy(button, true, 'Creating…');
    try {
      await request<Space>('/spaces', {
        method: 'POST',
        body: JSON.stringify({
          name: 'Focus Room',
          capacity: 4,
          base_hourly_rate_vnd: 100000,
          timezone_name: 'Asia/Ho_Chi_Minh',
        }),
      });
      showToast('Demo workspace created.');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (message === 'The demo space already exists.') {
        showToast('Demo workspace is already available.');
      } else {
        showToast(message, 'error');
      }
    } finally {
      await loadSpaces().catch(() => undefined);
      setButtonBusy(button, false, 'Create demo space');
    }
  });

  element<HTMLButtonElement>('#load').addEventListener('click', async (event) => {
    const button = event.currentTarget as HTMLButtonElement;
    setButtonBusy(button, true, 'Refreshing…');
    try {
      await loadSpaces();
      showToast('Workspace list refreshed.');
    } catch (error) {
      showToast(error instanceof Error ? error.message : String(error), 'error');
    } finally {
      setButtonBusy(button, false, 'Refresh');
    }
  });

  element<HTMLButtonElement>('#refresh-bookings').addEventListener('click', async (event) => {
    const button = event.currentTarget as HTMLButtonElement;
    setButtonBusy(button, true, 'Refreshing…');
    try {
      await loadBookings();
    } catch (error) {
      showToast(error instanceof Error ? error.message : String(error), 'error');
    } finally {
      setButtonBusy(button, false, 'Refresh');
    }
  });

  element<HTMLFormElement>('#quote-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    clearMessage('#booking-message');
    setButtonBusy(quoteButton, true, 'Calculating…');
    confirmButton.disabled = true;

    try {
      const payload = quotePayloadFromForm();
      const quote = await request<Quote>('/quotes', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      currentQuote = quote;
      currentQuotePayload = payload;
      renderQuote(quote);
      confirmButton.disabled = false;
    } catch (error) {
      clearQuote();
      showMessage('#booking-message', error instanceof Error ? error.message : String(error), 'error');
    } finally {
      setButtonBusy(quoteButton, false, 'Calculate quote');
    }
  });

  confirmButton.addEventListener('click', async () => {
    clearMessage('#booking-message');
    if (!currentQuote || !currentQuotePayload) {
      showMessage('#booking-message', 'Calculate a fresh quote before confirming.', 'error');
      return;
    }
    if (!customerInput.reportValidity()) return;

    setButtonBusy(confirmButton, true, 'Confirming…');
    try {
      const booking = await request<Booking>('/bookings', {
        method: 'POST',
        body: JSON.stringify({
          ...currentQuotePayload,
          customer_name: customerInput.value.trim(),
        }),
      });
      showMessage(
        '#booking-message',
        `Booking #${booking.id} confirmed for ${formatVnd(booking.total_price_vnd)}.`,
        'success',
      );
      showToast('Booking confirmed.');
      dayInput.value = localDateValue(new Date(currentQuotePayload.start_time));
      currentQuote = null;
      currentQuotePayload = null;
      element<HTMLDivElement>('#quote-card').hidden = true;
      await Promise.all([loadBookings(), loadAnalytics()]);
    } catch (error) {
      showMessage('#booking-message', error instanceof Error ? error.message : String(error), 'error');
    } finally {
      confirmButton.disabled = currentQuote === null;
      if (confirmButton.dataset.idleLabel) {
        confirmButton.textContent = confirmButton.dataset.idleLabel;
        delete confirmButton.dataset.idleLabel;
      }
    }
  });

  element<HTMLDivElement>('#booking-list').addEventListener('click', async (event) => {
    const target = event.target as HTMLElement;
    const button = target.closest<HTMLButtonElement>('[data-cancel-booking]');
    if (!button) return;
    const bookingId = Number(button.dataset.cancelBooking);
    if (!Number.isInteger(bookingId)) return;

    setButtonBusy(button, true, 'Cancelling…');
    try {
      await request(`/bookings/${bookingId}/cancel`, { method: 'PATCH' });
      showToast(`Booking #${bookingId} cancelled.`);
      await Promise.all([loadBookings(), loadAnalytics()]);
    } catch (error) {
      showToast(error instanceof Error ? error.message : String(error), 'error');
      setButtonBusy(button, false, 'Cancel');
    }
  });

  element<HTMLFormElement>('#analytics-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    setButtonBusy(analyticsButton, true, 'Loading…');
    clearMessage('#analytics-message');
    try {
      await loadAnalytics();
    } catch (error) {
      showMessage('#analytics-message', error instanceof Error ? error.message : String(error), 'error');
    } finally {
      setButtonBusy(analyticsButton, false, 'Load analytics');
    }
  });
}

async function initialize(): Promise<void> {
  setDefaultDates();
  try {
    await request<{ status: string }>('/health');
    setApiStatus(true);
    await Promise.all([loadSpaces(), loadBookings(), loadAnalytics()]);
  } catch (error) {
    setApiStatus(false);
    showToast(error instanceof Error ? error.message : String(error), 'error');
  }
}

void initialize();
