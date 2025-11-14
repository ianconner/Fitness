-- schema.sql
-- Add role column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'role') THEN
        ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';
    END IF;
END $$;

-- Ensure all existing users have role = 'user'
UPDATE users SET role = 'user' WHERE role IS NULL;

-- Rest of schema (safe to re-run)
DROP TABLE IF EXISTS workout_exercises, workouts, goals CASCADE;

CREATE TABLE IF NOT EXISTS goals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    exercise TEXT NOT NULL,
    metric_type TEXT NOT NULL CHECK (metric_type IN ('time_min', 'reps', 'weight_lbs', 'distance_mi')),
    target_value NUMERIC NOT NULL,
    target_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workouts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    workout_date DATE NOT NULL,
    notes TEXT NOT NULL,
    duration_min INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workout_exercises (
    id SERIAL PRIMARY KEY,
    workout_id INTEGER REFERENCES workouts(id) ON DELETE CASCADE,
    exercise TEXT NOT NULL,
    sets INTEGER,
    reps INTEGER,
    weight_lbs NUMERIC,
    time_min NUMERIC,
    rest_min NUMERIC,
    distance_mi NUMERIC
);
