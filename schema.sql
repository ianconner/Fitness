-- schema.sql
-- DROP AND RECREATE EVERYTHING SAFELY

-- Drop tables in correct order
DROP TABLE IF EXISTS workout_exercises CASCADE;
DROP TABLE IF EXISTS workouts CASCADE;
DROP TABLE IF EXISTS goals CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Create users with role
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create goals
CREATE TABLE goals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    exercise TEXT NOT NULL,
    metric_type TEXT NOT NULL CHECK (metric_type IN ('time_min', 'reps', 'weight_lbs', 'distance_mi')),
    target_value NUMERIC NOT NULL,
    target_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create workouts
CREATE TABLE workouts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    workout_date DATE NOT NULL,
    notes TEXT NOT NULL,
    duration_min INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create workout_exercises
CREATE TABLE workout_exercises (
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
