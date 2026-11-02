USE BankDB;

INSERT INTO Bank (Bank_Name, Head_Office, Contact_No, Email) VALUES
('State Bank of India', 'Mumbai', '1800-123-4567', 'contact@sbi.in'),
('HDFC Bank',           'Mumbai', '1800-765-4321', 'help@hdfc.in');

INSERT INTO Branch (Branch_Name, Address, City, IFSC_Code, Bank_ID) VALUES
('MG Road Branch',  '12 MG Road',      'Bangalore', 'SBIN0001', 1),
('Andheri Branch',  '45 Andheri West', 'Mumbai',    'SBIN0002', 1),
('Connaught Place', 'CP Circle',       'Delhi',     'HDFC0001', 2);

INSERT INTO Employee (Employee_Name, Email, Password, Branch_ID, Role) VALUES
('Alice Sharma', 'alice@sbi.in', 'PLACEHOLDER', 1, 'Manager'),
('Bob Verma',    'bob@hdfc.in',  'PLACEHOLDER', 2, 'Teller');

INSERT INTO Customer (Customer_Name, Phone_No, Email, Address, DOB, Password) VALUES
('Rahul Mehta',  '9876543210', 'rahul@mail.com', '12 Park St, Bangalore', '1990-05-12', 'PLACEHOLDER'),
('Priya Nair',   '9812345678', 'priya@mail.com', '88 Lake View, Mumbai',  '1985-11-23', 'PLACEHOLDER'),
('Arjun Rao',    '9900112233', 'arjun@mail.com', '5 Rose Garden, Delhi',  '1998-02-04', 'PLACEHOLDER'),
('Sneha Kapoor', '9700123456', 'sneha@mail.com', '9 Hill Rd, Bangalore',  '1993-08-19', 'PLACEHOLDER');

INSERT INTO Account (Customer_ID, Branch_ID, Account_Type, Balance, Status) VALUES
(1, 1, 'Savings', 25000.00,  'Active'),
(1, 1, 'Current',  8000.00,  'Active'),
(2, 2, 'Savings', 52000.50,  'Active'),
(3, 3, 'Savings',  3100.75,  'Active'),
(4, 1, 'Savings', 128000.00, 'Active');

INSERT INTO Loan (Customer_ID, Loan_Type, Amount, Interest_Rate, Duration_Months, Status) VALUES
(1, 'Home',      500000.00, 7.50,  240, 'Approved'),
(2, 'Car',       300000.00, 9.00,   60, 'Pending'),
(3, 'Education', 150000.00, 6.50,   48, 'Pending'),
(4, 'Personal',   80000.00, 11.00,  24, 'Approved');

INSERT INTO `Transaction` (Account_ID, Transaction_Date, Transaction_Type, Amount) VALUES
(1, CURDATE() - INTERVAL 6 DAY, 'Deposit',   5000.00),
(1, CURDATE() - INTERVAL 4 DAY, 'Withdraw',  1200.00),
(1, CURDATE() - INTERVAL 1 DAY, 'Deposit',   3000.00),
(3, CURDATE() - INTERVAL 3 DAY, 'Deposit',  10000.00),
(5, CURDATE(),                  'Deposit',  20000.00);

INSERT INTO Audit_Log (Actor, Action) VALUES ('system', 'Database seeded');
