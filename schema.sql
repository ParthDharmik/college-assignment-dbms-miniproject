DROP DATABASE IF EXISTS BankDB;
CREATE DATABASE BankDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE BankDB;

CREATE TABLE Bank (
    Bank_ID      INT PRIMARY KEY AUTO_INCREMENT,
    Bank_Name    VARCHAR(100) NOT NULL,
    Head_Office  VARCHAR(150),
    Contact_No   VARCHAR(20),
    Email        VARCHAR(100)
);

CREATE TABLE Branch (
    Branch_ID   INT PRIMARY KEY AUTO_INCREMENT,
    Branch_Name VARCHAR(100) NOT NULL,
    Address     VARCHAR(200),
    City        VARCHAR(80),
    IFSC_Code   VARCHAR(20),
    Bank_ID     INT NOT NULL,
    FOREIGN KEY (Bank_ID) REFERENCES Bank(Bank_ID) ON DELETE CASCADE
);

CREATE TABLE Employee (
    Employee_ID   INT PRIMARY KEY AUTO_INCREMENT,
    Employee_Name VARCHAR(100) NOT NULL,
    Email         VARCHAR(100),
    Password      VARCHAR(255) NOT NULL,
    Branch_ID     INT,
    Role          ENUM('Teller','Manager','Admin') DEFAULT 'Teller',
    FOREIGN KEY (Branch_ID) REFERENCES Branch(Branch_ID) ON DELETE SET NULL
);

CREATE TABLE Customer (
    Customer_ID   INT PRIMARY KEY AUTO_INCREMENT,
    Customer_Name VARCHAR(100) NOT NULL,
    Phone_No      VARCHAR(20),
    Email         VARCHAR(100),
    Address       VARCHAR(200),
    DOB           DATE,
    Password      VARCHAR(255) NOT NULL,
    Created_At    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Account (
    Account_ID   INT PRIMARY KEY AUTO_INCREMENT,
    Customer_ID  INT NOT NULL,
    Branch_ID    INT NOT NULL,
    Account_Type ENUM('Savings','Current','Fixed') DEFAULT 'Savings',
    Balance      DECIMAL(15,2) DEFAULT 0.00,
    Opening_Date DATE DEFAULT (CURRENT_DATE),
    Status       ENUM('Active','Closed','Frozen') DEFAULT 'Active',
    FOREIGN KEY (Customer_ID) REFERENCES Customer(Customer_ID) ON DELETE CASCADE,
    FOREIGN KEY (Branch_ID)   REFERENCES Branch(Branch_ID) ON DELETE CASCADE
);

CREATE TABLE Loan (
    Loan_ID         INT PRIMARY KEY AUTO_INCREMENT,
    Customer_ID     INT NOT NULL,
    Loan_Type       ENUM('Home','Car','Personal','Education','Business') NOT NULL,
    Amount          DECIMAL(15,2) NOT NULL,
    Interest_Rate   DECIMAL(5,2) DEFAULT 8.50,
    Duration_Months INT DEFAULT 12,
    Status          ENUM('Pending','Approved','Rejected') DEFAULT 'Pending',
    Created_At      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Customer_ID) REFERENCES Customer(Customer_ID) ON DELETE CASCADE
);

CREATE TABLE `Transaction` (
    Transaction_ID   INT PRIMARY KEY AUTO_INCREMENT,
    Account_ID       INT NOT NULL,
    Transaction_Date DATE DEFAULT (CURRENT_DATE),
    Transaction_Type ENUM('Deposit','Withdraw') NOT NULL,
    Amount           DECIMAL(15,2) NOT NULL,
    FOREIGN KEY (Account_ID) REFERENCES Account(Account_ID) ON DELETE CASCADE
);

CREATE TABLE Audit_Log (
    Log_ID     INT PRIMARY KEY AUTO_INCREMENT,
    Actor      VARCHAR(80),
    Action     VARCHAR(200),
    Created_At TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_account_customer ON Account(Customer_ID);
CREATE INDEX idx_account_branch   ON Account(Branch_ID);
CREATE INDEX idx_txn_account      ON `Transaction`(Account_ID);
CREATE INDEX idx_loan_customer    ON Loan(Customer_ID);
