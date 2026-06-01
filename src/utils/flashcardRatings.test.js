import { loadRatings, setRating } from './flashcardRatings';

// Mock localStorage
const store = {};
global.localStorage = {
  getItem: (k) => store[k] ?? null,
  setItem: (k, v) => { store[k] = v; },
  removeItem: (k) => { delete store[k]; },
};

beforeEach(() => { Object.keys(store).forEach(k => delete store[k]); });

test('loadRatings returns empty object when nothing stored', () => {
  expect(loadRatings('gen-1')).toEqual({});
});

test('setRating persists a rating and loadRatings reads it back', () => {
  setRating('gen-1', 2, 'up');
  expect(loadRatings('gen-1')).toEqual({ 2: 'up' });
});

test('setRating with null removes the rating', () => {
  setRating('gen-1', 2, 'up');
  setRating('gen-1', 2, null);
  expect(loadRatings('gen-1')).toEqual({});
});

test('ratings are scoped per generationId', () => {
  setRating('gen-1', 0, 'up');
  setRating('gen-2', 0, 'down');
  expect(loadRatings('gen-1')).toEqual({ 0: 'up' });
  expect(loadRatings('gen-2')).toEqual({ 0: 'down' });
});
