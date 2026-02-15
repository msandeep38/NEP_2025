-- ========================================================================================================
-- NEP 2020 ENHANCED TIMETABLE GENERATOR DATABASE SCHEMA - PRODUCTION READY
-- Government of Jharkhand - Generalized Scheduling Mechanism
-- Version: 2.0 Enhanced with Deterministic Algorithm Support
-- Database: PostgreSQL 15+
-- Last Updated: September 24, 2025
-- ========================================================================================================

-- SYSTEM CONFIGURATION
SET timezone = 'Asia/Kolkata';
SET default_transaction_isolation = 'serializable';

-- Required Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "ltree";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ========================================================================================================
-- ENUMERATION TYPES
-- ========================================================================================================

CREATE TYPE institution_type_enum AS ENUM ('UNIVERSITY', 'COLLEGE', 'INSTITUTE', 'AUTONOMOUS_COLLEGE');
CREATE TYPE program_type_enum AS ENUM ('UG', 'PG', 'DIPLOMA', 'CERTIFICATE', 'INTEGRATED', 'DOCTORAL');
CREATE TYPE course_type_enum AS ENUM ('CORE', 'ELECTIVE', 'SKILL_ENHANCEMENT', 'VALUE_ADDED', 'FOUNDATION');
CREATE TYPE nep_category_enum AS ENUM ('MAJOR', 'MINOR', 'MULTIDISCIPLINARY', 'SKILL_ENHANCEMENT', 'VALUE_ADDED');
CREATE TYPE faculty_designation_enum AS ENUM ('PROFESSOR', 'ASSOCIATE_PROF', 'ASSISTANT_PROF', 'LECTURER', 'VISITING_PROF');
CREATE TYPE employment_type_enum AS ENUM ('PERMANENT', 'CONTRACT', 'VISITING', 'GUEST', 'ADJUNCT');
CREATE TYPE room_type_enum AS ENUM ('CLASSROOM', 'LAB', 'SEMINAR', 'AUDITORIUM', 'LIBRARY', 'TUTORIAL');
CREATE TYPE shift_type_enum AS ENUM ('MORNING', 'AFTERNOON', 'EVENING', 'NIGHT', 'FLEXIBLE');
CREATE TYPE slot_type_enum AS ENUM ('REGULAR', 'LAB', 'EXAMINATION', 'SPECIAL', 'BREAK');
CREATE TYPE preferred_shift_enum AS ENUM ('MORNING', 'AFTERNOON', 'EVENING', 'ANY', 'FLEXIBLE');
CREATE TYPE parameter_data_type_enum AS ENUM ('STRING', 'INTEGER', 'DECIMAL', 'BOOLEAN', 'DATE', 'JSON', 'ARRAY');
CREATE TYPE constraint_type_enum AS ENUM ('HARD', 'SOFT', 'PREFERENCE', 'BUSINESS_RULE');
CREATE TYPE validation_status_enum AS ENUM ('PENDING', 'IN_PROGRESS', 'SUCCESS', 'FAILED', 'WARNING');
CREATE TYPE file_type_enum AS ENUM ('INSTITUTIONS', 'COURSES', 'FACULTY', 'ROOMS', 'TIMESLOTS', 'BATCHES', 'CONSTRAINTS');
CREATE TYPE validation_stage_enum AS ENUM ('SYNTAX', 'SEMANTIC', 'BUSINESS_RULES', 'CROSS_REFERENCE', 'FINGERPRINT');
CREATE TYPE scheduling_status_enum AS ENUM ('INITIALIZING', 'VALIDATING', 'FINGERPRINTING', 'OPTIMIZING', 'COMPLETED', 'FAILED', 'CANCELLED');
CREATE TYPE assignment_type_enum AS ENUM ('THEORY', 'PRACTICAL', 'TUTORIAL', 'LAB', 'SEMINAR', 'PROJECT');
CREATE TYPE algorithm_stage_enum AS ENUM ('FINGERPRINT', 'PRESEED', 'MAIN_SOLVER', 'REPAIR', 'VALIDATION', 'OUTPUT');
CREATE TYPE execution_status_enum AS ENUM ('RUNNING', 'COMPLETED', 'FAILED', 'TIMEOUT', 'CANCELLED');

-- ========================================================================================================
-- CORE INSTITUTIONAL TABLES
-- ========================================================================================================

-- 1. INSTITUTIONS - Multi-tenant institution management
CREATE TABLE institutions (
    institution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
    institution_name VARCHAR(255) NOT NULL,
    institution_code VARCHAR(50) UNIQUE NOT NULL,
    district_id UUID NOT NULL,
    state_code VARCHAR(10) DEFAULT 'JH',
    institution_type institution_type_enum NOT NULL DEFAULT 'COLLEGE',
    nep_compliance_level INTEGER CHECK (nep_compliance_level >= 0 AND nep_compliance_level <= 100) DEFAULT 80,
    supports_interdisciplinary BOOLEAN DEFAULT TRUE,
    supports_major_minor BOOLEAN DEFAULT TRUE,
    supports_multiple_entry_exit BOOLEAN DEFAULT TRUE,
    max_students_capacity INTEGER CHECK (max_students_capacity > 0),
    configuration_template JSONB DEFAULT '{}',
    academic_calendar JSONB DEFAULT '{}',
    language_preferences TEXT[] DEFAULT ARRAY['en', 'hi'],
    accreditation_details JSONB DEFAULT '{}',
    contact_info JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. DYNAMIC PARAMETERS - Unlimited parameter definitions using EAV pattern
CREATE TABLE dynamic_parameters (
    parameter_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    parameter_code VARCHAR(100) NOT NULL,
    parameter_name VARCHAR(255) NOT NULL,
    parameter_path LTREE NOT NULL,
    data_type parameter_data_type_enum NOT NULL DEFAULT 'STRING',
    validation_rules JSONB DEFAULT '{}',
    default_value TEXT,
    is_required BOOLEAN DEFAULT FALSE,
    is_system_parameter BOOLEAN DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE,
    UNIQUE(tenant_id, parameter_code)
);

-- 3. ENTITY PARAMETER VALUES - Dynamic parameter values for any entity
CREATE TABLE entity_parameter_values (
    value_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID NOT NULL,
    parameter_id UUID NOT NULL REFERENCES dynamic_parameters(parameter_id) ON DELETE CASCADE,
    value_text TEXT,
    value_numeric DECIMAL(15,4),
    value_integer INTEGER,
    value_boolean BOOLEAN,
    value_date DATE,
    value_json JSONB,
    effective_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    effective_to TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE
);

-- 4. DEPARTMENTS - Academic departments with cross-departmental support
CREATE TABLE departments (
    department_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    institution_id UUID NOT NULL REFERENCES institutions(institution_id) ON DELETE CASCADE,
    department_code VARCHAR(50) NOT NULL,
    department_name VARCHAR(255) NOT NULL,
    parent_department_id UUID REFERENCES departments(department_id),
    allows_cross_enrollment BOOLEAN DEFAULT TRUE,
    interdisciplinary_priority INTEGER DEFAULT 1 CHECK (interdisciplinary_priority >= 1 AND interdisciplinary_priority <= 10),
    head_of_department_id UUID,
    budget_allocation DECIMAL(15,2) DEFAULT 0,
    department_type VARCHAR(50) DEFAULT 'ACADEMIC',
    research_focus TEXT[] DEFAULT ARRAY[]::TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE,
    UNIQUE(tenant_id, department_code)
);

-- 5. PROGRAMS - Academic programs with major-minor combinations
CREATE TABLE programs (
    program_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    institution_id UUID NOT NULL REFERENCES institutions(institution_id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(department_id),
    program_code VARCHAR(50) NOT NULL,
    program_name VARCHAR(255) NOT NULL,
    program_type program_type_enum NOT NULL DEFAULT 'UG',
    is_multidisciplinary BOOLEAN DEFAULT FALSE,
    supports_minor BOOLEAN DEFAULT FALSE,
    supports_multiple_entry_exit BOOLEAN DEFAULT FALSE,
    duration_semesters INTEGER NOT NULL CHECK (duration_semesters > 0),
    min_credits_per_semester INTEGER DEFAULT 18 CHECK (min_credits_per_semester > 0),
    max_credits_per_semester INTEGER DEFAULT 26 CHECK (max_credits_per_semester >= min_credits_per_semester),
    total_credits_required INTEGER NOT NULL CHECK (total_credits_required > 0),
    program_objectives TEXT[] DEFAULT ARRAY[]::TEXT[],
    career_outcomes TEXT[] DEFAULT ARRAY[]::TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE,
    UNIQUE(tenant_id, program_code)
);

-- 6. COURSES - Course catalog with interdisciplinary features
CREATE TABLE courses (
    course_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    institution_id UUID NOT NULL REFERENCES institutions(institution_id) ON DELETE CASCADE,
    department_id UUID NOT NULL REFERENCES departments(department_id),
    course_code VARCHAR(50) NOT NULL,
    course_name VARCHAR(255) NOT NULL,
    course_type course_type_enum NOT NULL DEFAULT 'CORE',
    nep_category nep_category_enum NOT NULL DEFAULT 'MAJOR',
    credits DECIMAL(3,1) NOT NULL CHECK (credits > 0),
    theory_hours INTEGER DEFAULT 0 CHECK (theory_hours >= 0),
    practical_hours INTEGER DEFAULT 0 CHECK (practical_hours >= 0),
    tutorial_hours INTEGER DEFAULT 0 CHECK (tutorial_hours >= 0),
    self_study_hours INTEGER DEFAULT 0 CHECK (self_study_hours >= 0),
    prerequisites TEXT[] DEFAULT ARRAY[]::TEXT[],
    corequisites TEXT[] DEFAULT ARRAY[]::TEXT[],
    equipment_required TEXT[] DEFAULT ARRAY[]::TEXT[],
    software_required TEXT[] DEFAULT ARRAY[]::TEXT[],
    is_skill_enhancement BOOLEAN DEFAULT FALSE,
    is_value_added BOOLEAN DEFAULT FALSE,
    is_lab_required BOOLEAN DEFAULT FALSE,
    assessment_pattern JSONB DEFAULT '{}',
    learning_outcomes TEXT[] DEFAULT ARRAY[]::TEXT[],
    course_description TEXT,
    syllabus_outline JSONB DEFAULT '{}',
    textbooks JSONB DEFAULT '{}',
    reference_materials JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE,
    UNIQUE(tenant_id, course_code)
);

-- 7. FACULTY - Faculty management with cross-departmental teaching
CREATE TABLE faculty (
    faculty_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    institution_id UUID NOT NULL REFERENCES institutions(institution_id) ON DELETE CASCADE,
    primary_department_id UUID NOT NULL REFERENCES departments(department_id),
    faculty_code VARCHAR(50) NOT NULL,
    faculty_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(20),
    designation faculty_designation_enum NOT NULL DEFAULT 'ASSISTANT_PROF',
    employment_type employment_type_enum NOT NULL DEFAULT 'PERMANENT',
    can_teach_cross_department BOOLEAN DEFAULT FALSE,
    max_hours_per_week INTEGER DEFAULT 18 CHECK (max_hours_per_week > 0 AND max_hours_per_week <= 50),
    max_courses_per_semester INTEGER DEFAULT 4 CHECK (max_courses_per_semester > 0),
    preferred_subjects TEXT[] DEFAULT ARRAY[]::TEXT[],
    specializations TEXT[] DEFAULT ARRAY[]::TEXT[],
    qualifications JSONB DEFAULT '{}',
    experience_years INTEGER DEFAULT 0 CHECK (experience_years >= 0),
    availability_pattern JSONB DEFAULT '{}',
    preference_scores JSONB DEFAULT '{}',
    research_interests TEXT[] DEFAULT ARRAY[]::TEXT[],
    publications_count INTEGER DEFAULT 0,
    is_hod BOOLEAN DEFAULT FALSE,
    joining_date DATE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE,
    UNIQUE(tenant_id, faculty_code)
);

-- 8. ROOMS - Room management with shared resources
CREATE TABLE rooms (
    room_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    institution_id UUID NOT NULL REFERENCES institutions(institution_id) ON DELETE CASCADE,
    room_code VARCHAR(50) NOT NULL,
    room_name VARCHAR(255) NOT NULL,
    building_name VARCHAR(100),
    floor_number INTEGER DEFAULT 1,
    room_type room_type_enum NOT NULL DEFAULT 'CLASSROOM',
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    actual_capacity INTEGER, -- May differ from design capacity
    is_shared_resource BOOLEAN DEFAULT FALSE,
    equipment_available TEXT[] DEFAULT ARRAY[]::TEXT[],
    software_available TEXT[] DEFAULT ARRAY[]::TEXT[],
    department_access TEXT[] DEFAULT ARRAY[]::TEXT[],
    utilization_target DECIMAL(5,2) DEFAULT 75.00 CHECK (utilization_target > 0 AND utilization_target <= 100),
    maintenance_schedule JSONB DEFAULT '{}',
    booking_restrictions JSONB DEFAULT '{}',
    accessibility_features TEXT[] DEFAULT ARRAY[]::TEXT[],
    room_features JSONB DEFAULT '{}',
    is_air_conditioned BOOLEAN DEFAULT FALSE,
    has_projector BOOLEAN DEFAULT FALSE,
    has_smart_board BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE,
    UNIQUE(tenant_id, room_code)
);

-- 9. TIME_SLOTS - Time slot management with multi-shift support
CREATE TABLE time_slots (
    timeslot_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    institution_id UUID NOT NULL REFERENCES institutions(institution_id) ON DELETE CASCADE,
    slot_code VARCHAR(20) NOT NULL,
    slot_name VARCHAR(100),
    day_of_week INTEGER CHECK (day_of_week >= 1 AND day_of_week <= 7),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    shift_type shift_type_enum NOT NULL DEFAULT 'MORNING',
    slot_type slot_type_enum NOT NULL DEFAULT 'REGULAR',
    is_break_slot BOOLEAN DEFAULT FALSE,
    is_lunch_slot BOOLEAN DEFAULT FALSE,
    priority_level INTEGER DEFAULT 1 CHECK (priority_level >= 1 AND priority_level <= 10),
    duration_minutes INTEGER,
    buffer_time_minutes INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE,
    CONSTRAINT valid_time_range CHECK (end_time > start_time),
    UNIQUE(tenant_id, slot_code)
);

-- 10. STUDENT_BATCHES - Student batch management with flexible pathways
CREATE TABLE student_batches (
    batch_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    institution_id UUID NOT NULL REFERENCES institutions(institution_id) ON DELETE CASCADE,
    program_id UUID NOT NULL REFERENCES programs(program_id),
    batch_code VARCHAR(50) NOT NULL,
    batch_name VARCHAR(255) NOT NULL,
    academic_year VARCHAR(10) NOT NULL,
    current_semester INTEGER NOT NULL CHECK (current_semester > 0),
    student_count INTEGER NOT NULL CHECK (student_count > 0),
    has_minor_specialization BOOLEAN DEFAULT FALSE,
    minor_department_id UUID REFERENCES departments(department_id),
    supports_part_time BOOLEAN DEFAULT FALSE,
    max_classes_per_day INTEGER DEFAULT 8 CHECK (max_classes_per_day > 0 AND max_classes_per_day <= 12),
    preferred_shift preferred_shift_enum DEFAULT 'ANY',
    special_requirements JSONB DEFAULT '{}',
    class_representative_id UUID,
    batch_counselor_id UUID REFERENCES faculty(faculty_id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE,
    UNIQUE(tenant_id, batch_code)
);

-- ========================================================================================================
-- OPERATIONAL TABLES FOR DETERMINISTIC SCHEDULING
-- ========================================================================================================

-- 11. SESSION_LEARNING_OUTCOMES - Operationalize LO session mapping for NEP compliance
CREATE TABLE session_learning_outcomes (
    session_lo_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assignment_id UUID NOT NULL REFERENCES schedule_assignments(assignment_id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    lo_code VARCHAR(100) NOT NULL,
    coverage_percent DECIMAL(5,2) NOT NULL CHECK (coverage_percent >= 0 AND coverage_percent <= 100),
    actual_hours_delivered DECIMAL(4,2),
    assessment_mapped BOOLEAN DEFAULT FALSE,
    effectiveness_score DECIMAL(3,2) CHECK (effectiveness_score >= 0 AND effectiveness_score <= 5),
    delivery_method VARCHAR(50) DEFAULT 'LECTURE',
    resources_used TEXT[] DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(assignment_id, lo_code)
);

-- 12. ROOM_EQUIPMENT_BOOKING - Prevent equipment double-booking
CREATE TABLE room_equipment_booking (
    booking_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id UUID NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    timeslot_id UUID NOT NULL REFERENCES time_slots(timeslot_id) ON DELETE CASCADE,
    equipment_list TEXT[] DEFAULT ARRAY[]::TEXT[],
    reserved_by_assignment_id UUID REFERENCES schedule_assignments(assignment_id),
    booking_priority INTEGER DEFAULT 1 CHECK (booking_priority >= 1 AND booking_priority <= 10),
    reservation_type VARCHAR(20) DEFAULT 'AUTOMATIC' CHECK (reservation_type IN ('AUTOMATIC', 'MANUAL', 'EMERGENCY', 'MAINTENANCE')),
    booking_status VARCHAR(20) DEFAULT 'CONFIRMED' CHECK (booking_status IN ('CONFIRMED', 'CANCELLED', 'MODIFIED')),
    setup_time_minutes INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT room_equipment_unique UNIQUE (room_id, timeslot_id, reserved_by_assignment_id)
);

-- 13. LEARNING_OUTCOME_RESULTS - Post-assessment KPI closure for NEP compliance
CREATE TABLE learning_outcome_results (
    lo_result_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    batch_id UUID NOT NULL REFERENCES student_batches(batch_id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    lo_code VARCHAR(100) NOT NULL,
    session_lo_id UUID REFERENCES session_learning_outcomes(session_lo_id),
    assessment_score DECIMAL(5,2) CHECK (assessment_score >= 0 AND assessment_score <= 100),
    achieved BOOLEAN,
    assessment_date DATE,
    assessment_method VARCHAR(50),
    assessment_weightage DECIMAL(5,2) DEFAULT 100.0,
    gap_analysis JSONB DEFAULT '{}',
    remedial_action_required BOOLEAN DEFAULT FALSE,
    improvement_suggestions TEXT,
    assessor_id UUID REFERENCES faculty(faculty_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE
);

-- 14. RELAXATION_SUGGESTIONS - Minimal-relaxation engine output storage
CREATE TABLE relaxation_suggestions (
    suggestion_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES scheduling_sessions(session_id) ON DELETE CASCADE,
    constraint_id UUID REFERENCES dynamic_constraints(constraint_id),
    constraint_type VARCHAR(50) NOT NULL,
    affected_entities JSONB NOT NULL,
    description TEXT NOT NULL,
    cost_estimate DECIMAL(10,2) NOT NULL,
    projected_penalty_delta DECIMAL(10,2),
    administrative_impact VARCHAR(20) CHECK (administrative_impact IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    deterministic_rank INTEGER NOT NULL,
    approval_required BOOLEAN DEFAULT TRUE,
    approved_by UUID,
    approval_timestamp TIMESTAMP,
    implementation_notes TEXT,
    feasibility_score DECIMAL(3,2) DEFAULT 5.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 15. ALGORITHM_EXECUTION_LOG - Track algorithm performance
CREATE TABLE algorithm_execution_log (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES scheduling_sessions(session_id) ON DELETE CASCADE,
    algorithm_name VARCHAR(100) NOT NULL,
    execution_stage algorithm_stage_enum NOT NULL,
    start_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_timestamp TIMESTAMP,
    execution_status execution_status_enum DEFAULT 'RUNNING',
    input_parameters JSONB DEFAULT '{}',
    output_metrics JSONB DEFAULT '{}',
    error_details TEXT,
    memory_usage_mb INTEGER,
    cpu_time_seconds DECIMAL(8,3),
    deterministic_seed INTEGER,
    rule_version VARCHAR(20) DEFAULT 'v1',
    iterations_completed INTEGER DEFAULT 0,
    convergence_score DECIMAL(8,6),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 16. ASSIGNMENT_TRACE - Complete assignment auditability
CREATE TABLE assignment_trace (
    trace_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assignment_id UUID NOT NULL REFERENCES schedule_assignments(assignment_id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES scheduling_sessions(session_id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(course_id),
    faculty_id UUID NOT NULL REFERENCES faculty(faculty_id),
    room_id UUID NOT NULL REFERENCES rooms(room_id),
    timeslot_id UUID NOT NULL REFERENCES time_slots(timeslot_id),
    batch_id UUID NOT NULL REFERENCES student_batches(batch_id),
    primary_constraints_forced JSONB NOT NULL DEFAULT '[]',
    secondary_constraints_considered JSONB DEFAULT '[]',
    tie_breaker_used VARCHAR(100),
    assignment_rank INTEGER DEFAULT 1,
    fitness_contribution DECIMAL(10,4),
    conflicts_resolved JSONB DEFAULT '[]',
    alternative_assignments_considered JSONB DEFAULT '[]',
    algorithm_phase VARCHAR(50) DEFAULT 'UNKNOWN',
    decision_confidence DECIMAL(5,2) DEFAULT 0.0,
    decision_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================================================================
-- CONSTRAINT AND OPTIMIZATION TABLES
-- ========================================================================================================

-- 17. DYNAMIC_CONSTRAINTS - Runtime constraint definitions
CREATE TABLE dynamic_constraints (
    constraint_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    constraint_code VARCHAR(100) NOT NULL,
    constraint_name VARCHAR(255) NOT NULL,
    constraint_path LTREE NOT NULL,
    constraint_type constraint_type_enum NOT NULL DEFAULT 'HARD',
    constraint_expression TEXT NOT NULL,
    parameter_bindings JSONB DEFAULT '{}',
    weight DECIMAL(8,4) DEFAULT 1.0000 CHECK (weight >= 0),
    is_active BOOLEAN DEFAULT TRUE,
    violation_penalty DECIMAL(10,2) DEFAULT 100.00,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE,
    UNIQUE(tenant_id, constraint_code)
);

-- 18. CSV_IMPORT_SESSIONS - Track CSV compilation sessions
CREATE TABLE csv_import_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    session_name VARCHAR(255) NOT NULL,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    validation_status validation_status_enum DEFAULT 'PENDING',
    total_files INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    validation_errors JSONB DEFAULT '{}',
    compilation_rules JSONB DEFAULT '{}',
    created_by UUID NOT NULL,
    completed_at TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE
);

-- 19. CSV_FILE_VALIDATIONS - Individual file validation results
CREATE TABLE csv_file_validations (
    validation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES csv_import_sessions(session_id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_type file_type_enum NOT NULL,
    validation_stage validation_stage_enum NOT NULL,
    is_valid BOOLEAN DEFAULT FALSE,
    error_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    validation_details JSONB DEFAULT '{}',
    processed_rows INTEGER DEFAULT 0,
    total_rows INTEGER DEFAULT 0,
    file_size_bytes BIGINT DEFAULT 0,
    processing_time_ms INTEGER DEFAULT 0,
    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 20. SCHEDULING_SESSIONS - Optimization session tracking
CREATE TABLE scheduling_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    session_name VARCHAR(255) NOT NULL,
    algorithm_selected VARCHAR(100),
    problem_size_classification VARCHAR(20) CHECK (problem_size_classification IN ('SMALL', 'MEDIUM', 'LARGE', 'HUGE')),
    complexity_score DECIMAL(10,4),
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    status scheduling_status_enum DEFAULT 'INITIALIZING',
    optimization_parameters JSONB DEFAULT '{}',
    performance_metrics JSONB DEFAULT '{}',
    total_events_processed INTEGER DEFAULT 0,
    total_assignments_generated INTEGER DEFAULT 0,
    hard_constraint_violations INTEGER DEFAULT 0,
    soft_constraint_penalty DECIMAL(12,4) DEFAULT 0,
    overall_fitness_score DECIMAL(12,6),
    created_by UUID NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE
);

-- 21. SCHEDULE_ASSIGNMENTS - Generated schedule assignments (core output)
CREATE TABLE schedule_assignments (
    assignment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES scheduling_sessions(session_id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL,
    course_id UUID NOT NULL REFERENCES courses(course_id),
    faculty_id UUID NOT NULL REFERENCES faculty(faculty_id),
    room_id UUID NOT NULL REFERENCES rooms(room_id),
    timeslot_id UUID NOT NULL REFERENCES time_slots(timeslot_id),
    batch_id UUID NOT NULL REFERENCES student_batches(batch_id),
    assignment_type assignment_type_enum DEFAULT 'THEORY',
    solution_rank INTEGER DEFAULT 1,
    fitness_score DECIMAL(10,4),
    constraint_violations JSONB DEFAULT '{}',
    assignment_confidence DECIMAL(5,2) CHECK (assignment_confidence >= 0 AND assignment_confidence <= 100),
    is_optimal BOOLEAN DEFAULT FALSE,
    alternatives_available INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tenant_id) REFERENCES institutions(tenant_id) ON DELETE CASCADE
);

-- ========================================================================================================
-- RELATIONSHIP TABLES
-- ========================================================================================================

-- 22. COURSE_PREREQUISITES
CREATE TABLE course_prerequisites (
    prerequisite_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    prerequisite_course_id UUID NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    is_concurrent BOOLEAN DEFAULT FALSE,
    minimum_grade VARCHAR(5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(course_id, prerequisite_course_id)
);

-- 23. FACULTY_COURSE_COMPETENCY
CREATE TABLE faculty_course_competency (
    competency_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    faculty_id UUID NOT NULL REFERENCES faculty(faculty_id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    competency_level INTEGER CHECK (competency_level >= 1 AND competency_level <= 10) DEFAULT 5,
    can_teach_theory BOOLEAN DEFAULT TRUE,
    can_teach_practical BOOLEAN DEFAULT TRUE,
    can_teach_tutorial BOOLEAN DEFAULT TRUE,
    preference_score DECIMAL(3,2) CHECK (preference_score >= 0 AND preference_score <= 10) DEFAULT 5.0,
    teaching_experience_years INTEGER DEFAULT 0,
    last_taught_semester VARCHAR(10),
    certification_level VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(faculty_id, course_id)
);

-- 24. BATCH_COURSE_ENROLLMENT
CREATE TABLE batch_course_enrollment (
    enrollment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id UUID NOT NULL REFERENCES student_batches(batch_id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(course_id) ON DELETE CASCADE,
    credits_allocated DECIMAL(3,1) NOT NULL,
    is_mandatory BOOLEAN DEFAULT TRUE,
    priority_level INTEGER DEFAULT 1 CHECK (priority_level >= 1 AND priority_level <= 10),
    special_requirements JSONB DEFAULT '{}',
    enrollment_date DATE DEFAULT CURRENT_DATE,
    expected_completion_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(batch_id, course_id)
);

-- ========================================================================================================
-- MATERIALIZED VIEWS FOR PERFORMANCE
-- ========================================================================================================

-- Enhanced Faculty Workload Summary
CREATE MATERIALIZED VIEW faculty_workload_summary AS
SELECT
    f.tenant_id,
    f.faculty_id,
    f.faculty_code,
    f.faculty_name,
    f.designation,
    date_trunc('week', sa.created_at) as week_start,
    COUNT(DISTINCT sa.assignment_id) AS total_assignments,
    COUNT(DISTINCT sa.course_id) AS unique_courses_taught,
    COUNT(DISTINCT sa.batch_id) AS unique_batches_taught,
    SUM(ts.duration_minutes) / 60.0 AS total_hours_week,
    COUNT(DISTINCT c.department_id) AS departments_taught,
    CASE WHEN COUNT(DISTINCT c.department_id) > 1 THEN TRUE ELSE FALSE END AS is_cross_department_teaching,
    COUNT(CASE WHEN c.nep_category = 'MULTIDISCIPLINARY' THEN 1 END) AS multidisciplinary_courses,
    COUNT(CASE WHEN c.course_type = 'SKILL_ENHANCEMENT' THEN 1 END) AS skill_enhancement_courses,
    COALESCE((SUM(ts.duration_minutes) / 60.0) / NULLIF(f.max_hours_per_week, 0) * 100, 0) AS utilization_percentage,
    AVG(fcc.preference_score) AS avg_preference_satisfaction,
    CURRENT_TIMESTAMP as last_calculated
FROM faculty f
LEFT JOIN schedule_assignments sa ON f.faculty_id = sa.faculty_id
LEFT JOIN time_slots ts ON sa.timeslot_id = ts.timeslot_id  
LEFT JOIN courses c ON sa.course_id = c.course_id
LEFT JOIN faculty_course_competency fcc ON f.faculty_id = fcc.faculty_id AND c.course_id = fcc.course_id
GROUP BY f.tenant_id, f.faculty_id, f.faculty_code, f.faculty_name, f.designation, week_start, f.max_hours_per_week;

-- Enhanced Batch Workload Summary
CREATE MATERIALIZED VIEW batch_workload_summary AS
SELECT
    sb.tenant_id,
    sb.batch_id,
    sb.batch_code,
    sb.batch_name,
    sb.current_semester,
    ts.day_of_week,
    COUNT(sa.assignment_id) AS classes_per_day,
    COUNT(DISTINCT sa.course_id) AS unique_courses_per_day,
    COUNT(DISTINCT sa.faculty_id) AS unique_faculty_per_day,
    COUNT(DISTINCT sa.room_id) AS rooms_used_per_day,
    SUM(ts.duration_minutes) / 60.0 AS hours_per_day,
    COUNT(CASE WHEN c.nep_category = 'MULTIDISCIPLINARY' THEN 1 END) AS multidisciplinary_classes,
    COUNT(CASE WHEN c.course_type = 'SKILL_ENHANCEMENT' THEN 1 END) AS skill_enhancement_classes,
    CASE 
        WHEN COUNT(sa.assignment_id) > sb.max_classes_per_day THEN 'VIOLATION'
        WHEN COUNT(sa.assignment_id) = sb.max_classes_per_day THEN 'AT_LIMIT' 
        ELSE 'WITHIN_LIMIT'
    END AS daily_class_limit_status,
    CURRENT_TIMESTAMP as last_calculated
FROM student_batches sb
LEFT JOIN schedule_assignments sa ON sb.batch_id = sa.batch_id  
LEFT JOIN time_slots ts ON sa.timeslot_id = ts.timeslot_id
LEFT JOIN courses c ON sa.course_id = c.course_id
GROUP BY sb.tenant_id, sb.batch_id, sb.batch_code, sb.batch_name, sb.current_semester, ts.day_of_week, sb.max_classes_per_day;

-- Resource Utilization Summary
CREATE MATERIALIZED VIEW resource_utilization_summary AS
SELECT
    r.tenant_id,
    r.room_id,
    r.room_code,
    r.room_name,
    r.room_type,
    r.capacity,
    COUNT(sa.assignment_id) AS total_assignments,
    COUNT(DISTINCT ts.day_of_week) AS days_utilized,
    COUNT(DISTINCT DATE_TRUNC('week', sa.created_at)) AS weeks_active,
    SUM(ts.duration_minutes) / 60.0 AS total_hours_utilized,
    COALESCE(
        ROUND(
            (SUM(ts.duration_minutes) / 60.0) / 
            NULLIF((SELECT COUNT(*) * AVG(duration_minutes) / 60.0 FROM time_slots WHERE tenant_id = r.tenant_id), 0) * 100, 2
        ), 0
    ) AS utilization_percentage,
    CASE 
        WHEN COALESCE(
            (SUM(ts.duration_minutes) / 60.0) / 
            NULLIF((SELECT COUNT(*) * AVG(duration_minutes) / 60.0 FROM time_slots WHERE tenant_id = r.tenant_id), 0) * 100, 0
        ) >= r.utilization_target THEN 'MEETING_TARGET'
        ELSE 'BELOW_TARGET'
    END AS target_compliance,
    CURRENT_TIMESTAMP as last_calculated
FROM rooms r
LEFT JOIN schedule_assignments sa ON r.room_id = sa.room_id
LEFT JOIN time_slots ts ON sa.timeslot_id = ts.timeslot_id
GROUP BY r.tenant_id, r.room_id, r.room_code, r.room_name, r.room_type, r.capacity, r.utilization_target;

-- ========================================================================================================
-- COMPREHENSIVE INDEXING FOR PERFORMANCE
-- ========================================================================================================

-- Primary entity indexes
CREATE INDEX idx_institutions_tenant ON institutions(tenant_id);
CREATE INDEX idx_institutions_code ON institutions(institution_code);
CREATE INDEX idx_institutions_type ON institutions(institution_type, is_active);

-- Dynamic parameters indexes
CREATE INDEX idx_dynamic_parameters_tenant ON dynamic_parameters(tenant_id);
CREATE INDEX idx_dynamic_parameters_path ON dynamic_parameters USING GIST(parameter_path);
CREATE INDEX idx_dynamic_parameters_lookup ON dynamic_parameters(tenant_id, parameter_code, is_active);

-- Entity parameter values indexes
CREATE INDEX idx_entity_parameter_values_tenant ON entity_parameter_values(tenant_id);
CREATE INDEX idx_entity_parameter_values_entity ON entity_parameter_values(entity_type, entity_id);
CREATE INDEX idx_entity_parameter_values_active ON entity_parameter_values(parameter_id) WHERE effective_to IS NULL;

-- Department and program indexes
CREATE INDEX idx_departments_tenant ON departments(tenant_id);
CREATE INDEX idx_departments_institution ON departments(institution_id, is_active);
CREATE INDEX idx_programs_tenant ON programs(tenant_id);
CREATE INDEX idx_programs_department ON programs(department_id, is_active);

-- Course indexes
CREATE INDEX idx_courses_tenant ON courses(tenant_id);
CREATE INDEX idx_courses_department ON courses(department_id, is_active);
CREATE INDEX idx_courses_type ON courses(course_type, nep_category);
CREATE INDEX idx_courses_code ON courses(tenant_id, course_code);

-- Faculty indexes
CREATE INDEX idx_faculty_tenant ON faculty(tenant_id);
CREATE INDEX idx_faculty_department ON faculty(primary_department_id, is_active);
CREATE INDEX idx_faculty_designation ON faculty(designation, employment_type);
CREATE INDEX idx_faculty_cross_dept ON faculty(can_teach_cross_department) WHERE can_teach_cross_department = true;

-- Room indexes
CREATE INDEX idx_rooms_tenant ON rooms(tenant_id);
CREATE INDEX idx_rooms_type ON rooms(room_type, is_active);
CREATE INDEX idx_rooms_capacity ON rooms(capacity, room_type);
CREATE INDEX idx_rooms_building ON rooms(building_name, floor_number);

-- Time slot indexes
CREATE INDEX idx_time_slots_tenant ON time_slots(tenant_id);
CREATE INDEX idx_time_slots_day ON time_slots(day_of_week, shift_type, is_active);
CREATE INDEX idx_time_slots_time ON time_slots(start_time, end_time);

-- Student batch indexes
CREATE INDEX idx_student_batches_tenant ON student_batches(tenant_id);
CREATE INDEX idx_student_batches_program ON student_batches(program_id, is_active);
CREATE INDEX idx_student_batches_academic_year ON student_batches(academic_year, current_semester);

-- Operational table indexes
CREATE INDEX idx_session_lo_assignment ON session_learning_outcomes(assignment_id);
CREATE INDEX idx_session_lo_course_code ON session_learning_outcomes(course_id, lo_code);

CREATE INDEX idx_equipment_booking_room_time ON room_equipment_booking(room_id, timeslot_id);
CREATE INDEX idx_equipment_booking_assignment ON room_equipment_booking(reserved_by_assignment_id);

CREATE INDEX idx_learning_outcome_results_batch ON learning_outcome_results(batch_id, course_id);
CREATE INDEX idx_learning_outcome_results_assessment ON learning_outcome_results(assessment_date, achieved);

CREATE INDEX idx_relaxation_suggestions_session ON relaxation_suggestions(session_id);
CREATE INDEX idx_relaxation_suggestions_rank ON relaxation_suggestions(deterministic_rank, administrative_impact);

CREATE INDEX idx_algorithm_execution_session ON algorithm_execution_log(session_id);
CREATE INDEX idx_algorithm_execution_stage ON algorithm_execution_log(algorithm_name, execution_stage);

CREATE INDEX idx_assignment_trace_session ON assignment_trace(session_id);
CREATE INDEX idx_assignment_trace_assignment ON assignment_trace(assignment_id);

-- Constraint and scheduling indexes
CREATE INDEX idx_dynamic_constraints_active ON dynamic_constraints(tenant_id, constraint_type, is_active) WHERE is_active = true;
CREATE INDEX idx_csv_import_sessions_tenant ON csv_import_sessions(tenant_id, validation_status);
CREATE INDEX idx_scheduling_sessions_performance ON scheduling_sessions(algorithm_selected, problem_size_classification, status);
CREATE INDEX idx_schedule_assignments_composite ON schedule_assignments(session_id, tenant_id, assignment_type, solution_rank);

-- Relationship table indexes
CREATE INDEX idx_course_prerequisites_course ON course_prerequisites(course_id);
CREATE INDEX idx_faculty_course_competency_faculty ON faculty_course_competency(faculty_id);
CREATE INDEX idx_faculty_course_competency_course ON faculty_course_competency(course_id);
CREATE INDEX idx_batch_course_enrollment_batch ON batch_course_enrollment(batch_id);
CREATE INDEX idx_batch_course_enrollment_course ON batch_course_enrollment(course_id);

-- ========================================================================================================
-- TRIGGERS AND FUNCTIONS
-- ========================================================================================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_institutions_updated_at BEFORE UPDATE ON institutions
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Calculate duration for time slots
CREATE OR REPLACE FUNCTION calculate_duration_minutes()
RETURNS TRIGGER AS $$
BEGIN
    NEW.duration_minutes := EXTRACT(EPOCH FROM (NEW.end_time - NEW.start_time))/60;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_time_slots_duration BEFORE INSERT OR UPDATE ON time_slots
FOR EACH ROW EXECUTE FUNCTION calculate_duration_minutes();

-- Automatic LO session mapping
CREATE OR REPLACE FUNCTION auto_create_lo_sessions()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO session_learning_outcomes (assignment_id, course_id, lo_code, coverage_percent)
    SELECT 
        NEW.assignment_id,
        NEW.course_id,
        UNNEST(c.learning_outcomes) as lo_code,
        ROUND(100.0 / GREATEST(1, array_length(c.learning_outcomes, 1)), 2) as coverage_percent
    FROM courses c 
    WHERE c.course_id = NEW.course_id
    AND c.learning_outcomes IS NOT NULL
    AND array_length(c.learning_outcomes, 1) > 0;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_auto_lo_mapping 
    AFTER INSERT ON schedule_assignments
    FOR EACH ROW 
    EXECUTE FUNCTION auto_create_lo_sessions();

-- Equipment booking validation
CREATE OR REPLACE FUNCTION validate_equipment_booking()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.equipment_list IS NOT NULL AND array_length(NEW.equipment_list, 1) > 0 THEN
        IF NOT (
            SELECT bool_and(equipment = ANY(r.equipment_available))
            FROM UNNEST(NEW.equipment_list) as equipment
            JOIN rooms r ON r.room_id = NEW.room_id
        ) THEN
            RAISE EXCEPTION 'Equipment % not available in room %', 
                NEW.equipment_list, NEW.room_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_validate_equipment 
    BEFORE INSERT OR UPDATE ON room_equipment_booking
    FOR EACH ROW 
    EXECUTE FUNCTION validate_equipment_booking();

-- Assignment trace creation  
CREATE OR REPLACE FUNCTION create_assignment_trace()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO assignment_trace (
        assignment_id, session_id, course_id, faculty_id, room_id, 
        timeslot_id, batch_id, algorithm_phase, assigned_at
    ) VALUES (
        NEW.assignment_id, NEW.session_id, NEW.course_id, NEW.faculty_id, 
        NEW.room_id, NEW.timeslot_id, NEW.batch_id, 'UNKNOWN', NOW()
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_create_assignment_trace 
    AFTER INSERT ON schedule_assignments
    FOR EACH ROW 
    EXECUTE FUNCTION create_assignment_trace();

-- Materialized view refresh on scheduling completion
CREATE OR REPLACE FUNCTION refresh_workload_views()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'COMPLETED' AND OLD.status != 'COMPLETED' THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY faculty_workload_summary;
        REFRESH MATERIALIZED VIEW CONCURRENTLY batch_workload_summary;
        REFRESH MATERIALIZED VIEW CONCURRENTLY resource_utilization_summary;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_refresh_views 
    AFTER UPDATE ON scheduling_sessions
    FOR EACH ROW 
    EXECUTE FUNCTION refresh_workload_views();

-- ========================================================================================================
-- ROW LEVEL SECURITY FOR MULTI-TENANCY
-- ========================================================================================================

-- Enable RLS on all tenant-aware tables
ALTER TABLE institutions ENABLE ROW LEVEL SECURITY;
ALTER TABLE dynamic_parameters ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_parameter_values ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE programs ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE faculty ENABLE ROW LEVEL SECURITY;
ALTER TABLE rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE time_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE dynamic_constraints ENABLE ROW LEVEL SECURITY;
ALTER TABLE csv_import_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduling_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedule_assignments ENABLE ROW LEVEL SECURITY;

-- Tenant isolation policies
CREATE POLICY tenant_isolation_institutions ON institutions
FOR ALL TO public
USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_departments ON departments
FOR ALL TO public
USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_programs ON programs
FOR ALL TO public
USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_courses ON courses
FOR ALL TO public
USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_faculty ON faculty
FOR ALL TO public
USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_rooms ON rooms
FOR ALL TO public
USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_time_slots ON time_slots
FOR ALL TO public
USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_student_batches ON student_batches
FOR ALL TO public
USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE POLICY tenant_isolation_schedule_assignments ON schedule_assignments
FOR ALL TO public
USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- ========================================================================================================
-- SCHEMA VALIDATION AND CONSTRAINTS
-- ========================================================================================================

-- Additional business rule constraints
ALTER TABLE courses ADD CONSTRAINT valid_total_hours 
    CHECK ((theory_hours + practical_hours + tutorial_hours) > 0);

ALTER TABLE faculty ADD CONSTRAINT valid_email 
    CHECK (email IS NULL OR email ~* '^[A-Za-z0-9._%-]+@[A-Za-z0-9.-]+[.][A-Za-z]+$');

ALTER TABLE rooms ADD CONSTRAINT valid_actual_capacity 
    CHECK (actual_capacity IS NULL OR actual_capacity <= capacity);

ALTER TABLE student_batches ADD CONSTRAINT valid_semester 
    CHECK (current_semester <= (SELECT duration_semesters FROM programs WHERE program_id = student_batches.program_id));

ALTER TABLE batch_course_enrollment ADD CONSTRAINT valid_credits
    CHECK (credits_allocated > 0 AND credits_allocated <= (SELECT credits FROM courses WHERE course_id = batch_course_enrollment.course_id));

-- ========================================================================================================
-- PERFORMANCE OPTIMIZATION
-- ========================================================================================================

-- Create unique indexes for frequently queried combinations
CREATE UNIQUE INDEX idx_faculty_course_competency_unique ON faculty_course_competency(faculty_id, course_id);
CREATE UNIQUE INDEX idx_batch_course_enrollment_unique ON batch_course_enrollment(batch_id, course_id);

-- Partial indexes for active records
CREATE INDEX idx_courses_active ON courses(tenant_id, department_id) WHERE is_active = true;
CREATE INDEX idx_faculty_active ON faculty(tenant_id, primary_department_id) WHERE is_active = true;
CREATE INDEX idx_rooms_active ON rooms(tenant_id, room_type) WHERE is_active = true;
CREATE INDEX idx_time_slots_active ON time_slots(tenant_id, day_of_week, shift_type) WHERE is_active = true;

-- Statistics and maintenance
ANALYZE;

-- ========================================================================================================
-- SCHEMA DEPLOYMENT COMPLETE
-- ========================================================================================================

-- Final validation queries
DO $$
BEGIN
    RAISE NOTICE 'Schema deployment completed successfully at %', CURRENT_TIMESTAMP;
    RAISE NOTICE 'Total tables created: %', (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE');
    RAISE NOTICE 'Total indexes created: %', (SELECT count(*) FROM pg_indexes WHERE schemaname = 'public');
    RAISE NOTICE 'Total triggers created: %', (SELECT count(*) FROM information_schema.triggers WHERE trigger_schema = 'public');
END $$;

-- ========================================================================================================
-- END OF SCHEMA
-- ========================================================================================================
