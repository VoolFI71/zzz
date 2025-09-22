using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;

namespace Bakery
{
    class Program
    {
        static void Main(string[] args)
        {
            int kTime = 1;
            int kLife = 1;

            List<Product> products = new List<Product>
            {
                new Product("улитка с мясом", 6, 100, 6 * kTime, 4 * kLife),
                new Product("улитка со шпинатом и сыром", 4, 100, 6 * kTime, 4 * kLife),
                new Product("слойка с сахаром", 20, 50, 3 * kTime, 5 * kLife),
                new Product("слойка с малиной", 10, 40, 5 * kTime, 3 * kLife),
            };

            List<Employee> employees = new List<Employee>
            {
                new Director("Глеб", 105000),
                new Baker("Кирилл", 50000),
                new Cashier("Дима", 50000),
            };

            Bakery bakery = new Bakery("Междубулочье", products, employees);

            Console.WriteLine("Добро пожаловать в пекарню!");
            Console.Write("Выберите роль (разработчик/игрок): ");
            string role = (Console.ReadLine() ?? "").Trim().ToLower();

            Client client = null;
            if (role == "игрок" || role == "player" || role == "и")
            {
                Console.Write("Ваш ник: ");
                string name = (Console.ReadLine() ?? "").Trim();
                Console.Write("Баланс: ");
                string cashStr = (Console.ReadLine() ?? "0").Trim();
                int cash = 0;
                int.TryParse(cashStr, out cash);
                client = new Client(name, cash);
            }

            bakery.Start();
            Utils.Wait(1, "");

            if (client != null)
            {
                bakery.CashierSays("Здравствуйте! Что будете брать?");
                while (true)
                {
                    string choice = (Console.ReadLine() ?? "").Trim();
                    if (bakery.HandleChoice(choice, client) == "stop") break;
                    bakery.CashierSays("Что ещё?");
                }

                if (client.OrderAmount > 0)
                {
                    if (client.OrderAmount <= client.Cash)
                        bakery.CashierSays("Оплата прошла");
                    else
                        bakery.CashierSays("Недостаточно средств, вас попросят уйти");
                }

                if (!string.IsNullOrEmpty(client.Complaint))
                {
                    if (client.Complaint == "пекарь")
                        bakery.Employees[1] = Director.RemoveEmployee(bakery.Employees[1]);
                    else
                        bakery.Employees[2] = Director.RemoveEmployee(bakery.Employees[2]);
                }

                bakery.CashierSays($"Всего доброго, {client.Name}!");
            }
        }
    }

    static class Utils
    {
        public static void Wait(int seconds, string text = null)
        {
            if (!string.IsNullOrEmpty(text)) Console.Write(text);
            for (int i = 0; i < seconds; i++)
            {
                Thread.Sleep(1000);
                Console.Write(".");
            }
            Console.WriteLine();
        }
    }

    // ---- Entities ----
    class Employee
    {
        public virtual string Position => "Работник";
        public string Name { get; set; }
        public int Salary { get; set; }

        public Employee(string name, int salary)
        {
            this.Name = name;
            this.Salary = salary;
        }
    }

    class Director : Employee
    {
        public override string Position => "Директор";
        public Director(string name, int salary) : base(name, salary) { }

        // Возвращаем Employee (null если уволен)
        public static Employee RemoveEmployee(Employee emp)
        {
            if (emp is Baker || emp is Cashier)
            {
                Console.WriteLine($"Сотрудник {emp.Name} уволен");
                return null;
            }
            Console.WriteLine($"Нельзя уволить {emp.Name}");
            return emp;
        }
    }

    class Cashier : Employee
    {
        public override string Position => "Кассир";
        public Cashier(string name, int salary) : base(name, salary) { }
    }

    class Baker : Employee
    {
        public override string Position => "Пекарь";
        public Baker(string name, int salary) : base(name, salary) { }
    }

    class Product
    {
        public string Name { get; set; }
        public int Quantity { get; set; }
        public int Price { get; set; }
        public int CookTime { get; set; }
        public int ShelfLife { get; set; }

        public Product(string name, int quantity, int price, int cookTime, int shelfLife)
        {
            this.Name = name;
            this.Quantity = quantity;
            this.Price = price;
            this.CookTime = cookTime;
            this.ShelfLife = shelfLife;
        }
    }

    class Bakery
    {
        public string Name { get; set; }
        public List<Product> Products { get; set; }
        public List<Employee> Employees { get; set; } // [director, baker, cashier]

        public Bakery(string name, List<Product> products, List<Employee> employees)
        {
            this.Name = name;
            this.Products = products;
            this.Employees = employees;
        }

        public void Start()
        {
            Console.WriteLine($"Вы в пекарне \"{this.Name}\"");
        }

        public void CashierSays(string text)
        {
            Employee cashier = null;
            if (this.Employees != null && this.Employees.Count > 2) cashier = this.Employees[2];
            if (cashier != null)
                Console.WriteLine($"{cashier.Name}: {text}");
            else
                Console.WriteLine("Нет кассира.");
        }

        public void BakerSays(string text)
        {
            Employee baker = null;
            if (this.Employees != null && this.Employees.Count > 1) baker = this.Employees[1];
            if (baker != null)
                Console.WriteLine($"{baker.Name}: {text}");
            else
                Console.WriteLine("Нет пекаря.");
        }

        public string HandleChoice(string text, Client client)
        {
            text = (text ?? "").ToLower().Trim();
            if (text == "нет" || text == "ничего" || text == "не") return "stop";

            if (text == "хочу пожаловаться")
            {
                CashierSays("Кого вы хотите пожаловаться? (пекарь/кассир)");
                string who = (Console.ReadLine() ?? "").Trim().ToLower();
                if (who == "пекарь" || who == "кассир")
                {
                    client.Complaint = who;
                    CashierSays("Принял.");
                }
                return "";
            }

            Product prod = this.Products.FirstOrDefault(p => p.Name.ToLower() == text);
            if (prod == null)
            {
                CashierSays("Не понял, повторите.");
                return "";
            }

            CashierSays("Сколько?");
            string amountStr = (Console.ReadLine() ?? "0").Trim();
            if (!int.TryParse(amountStr, out int amount))
            {
                CashierSays("Неверно введено число.");
                return "";
            }

            if (amount > prod.Quantity)
            {
                CashierSays("Недостаточно, печатаем ещё.");
                BakerSays("Готовлю");
                Thread.Sleep(prod.CookTime * 1000);
                prod.Quantity += 10;
                BakerSays("Готово");
            }

            prod.Quantity -= amount;
            client.OrderAmount += prod.Price * amount;
            return "";
        }
    }

    class Client
    {
        public string Name { get; set; }
        public int Cash { get; set; }
        public int OrderAmount { get; set; }
        public string Complaint { get; set; }

        public Client(string name, int cash)
        {
            this.Name = name;
            this.Cash = cash;
            this.OrderAmount = 0;
            this.Complaint = null;
        }
    }
}
